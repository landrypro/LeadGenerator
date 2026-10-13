"""Worker atomique de projection Billing P53-05.

Revision ID: 20261009_0053
Revises: 20261009_0052
Create Date: 2026-10-09
"""

from alembic import op

revision = "20261009_0053"
down_revision = "20261009_0052"
branch_labels = None
depends_on = None

_CLAIM_SIGNATURE = "app_private.claim_billing_event()"
_PROJECT_SIGNATURE = "app_private.project_billing_event(uuid)"
_FAIL_SIGNATURE = "app_private.fail_billing_event_projection(uuid)"


def upgrade() -> None:
    op.execute(
        r"""
        CREATE FUNCTION app_private.claim_billing_event()
        RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_id uuid;
        BEGIN
          UPDATE public.billing_event_inbox
          SET status = 'dead_letter', last_error_code = 'projection_attempts_exhausted',
              processed_at = clock_timestamp(), updated_at = clock_timestamp()
          WHERE status = 'processing'
            AND processing_started_at < clock_timestamp() - interval '90 seconds'
            AND attempt_count >= 8;
          WITH candidate AS (
            SELECT id FROM public.billing_event_inbox
            WHERE (
              status = 'admitted' AND (next_attempt_at IS NULL OR next_attempt_at <= clock_timestamp())
            ) OR (
              status = 'processing' AND processing_started_at < clock_timestamp() - interval '90 seconds'
                AND attempt_count < 8
            )
            ORDER BY received_at, id
            FOR UPDATE SKIP LOCKED
            LIMIT 1
          )
          UPDATE public.billing_event_inbox AS inbox
          SET status = 'processing', attempt_count = inbox.attempt_count + 1,
              processing_started_at = clock_timestamp(), next_attempt_at = NULL,
              last_error_code = NULL, updated_at = clock_timestamp()
          FROM candidate
          WHERE inbox.id = candidate.id
          RETURNING inbox.id INTO v_id;
          RETURN v_id;
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.project_billing_event(p_inbox_id uuid)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_inbox public.billing_event_inbox%ROWTYPE;
          v_subscription_id uuid;
          v_organization_id uuid;
          v_plan_version_id uuid;
          v_plan_version_state text;
          v_customer_reference text;
          v_current_state text;
          v_next_state text;
          v_payload_state text;
          v_payload_currency text;
          v_period_start timestamptz;
          v_period_end timestamptz;
          v_provider_updated_at timestamptz;
          v_cancel_at_period_end boolean;
          v_billing_event_id uuid;
          v_cause text;
          v_request_id text;
        BEGIN
          SELECT * INTO v_inbox FROM public.billing_event_inbox
          WHERE id = p_inbox_id FOR UPDATE;
          IF NOT FOUND OR v_inbox.status <> 'processing' THEN
            RETURN jsonb_build_object('result_code', 'lost_claim');
          END IF;
          IF v_inbox.event_type = 'refund.succeeded' THEN
            UPDATE public.billing_event_inbox
            SET status='ignored', last_error_code='refund_policy_deferred', processed_at=clock_timestamp(), updated_at=clock_timestamp()
            WHERE id=v_inbox.id;
            RETURN jsonb_build_object('result_code', 'ignored');
          END IF;
          v_customer_reference := v_inbox.normalized_payload #>> '{subscription,customer_reference}';
          IF v_customer_reference IS NULL THEN
            UPDATE public.billing_event_inbox
            SET status='ignored', last_error_code='billing_mapping_missing', processed_at=clock_timestamp(), updated_at=clock_timestamp()
            WHERE id=v_inbox.id;
            RETURN jsonb_build_object('result_code', 'ignored');
          END IF;
          SELECT subscription.id, subscription.organization_id, subscription.plan_version_id, subscription.state,
                 plan_version.state
          INTO v_subscription_id, v_organization_id, v_plan_version_id, v_current_state, v_plan_version_state
          FROM public.subscriptions AS subscription
          JOIN public.billing_customers AS customer
            ON customer.id=subscription.billing_customer_id AND customer.organization_id=subscription.organization_id
          JOIN public.plan_versions AS plan_version ON plan_version.id=subscription.plan_version_id
          WHERE subscription.provider=v_inbox.provider
            AND subscription.provider_subscription_reference=(v_inbox.normalized_payload #>> '{subscription,reference}')
            AND customer.provider=v_inbox.provider
            AND customer.provider_customer_reference=v_customer_reference
          FOR UPDATE OF subscription;
          IF NOT FOUND THEN
            UPDATE public.billing_event_inbox
            SET status='ignored', last_error_code='billing_mapping_missing', processed_at=clock_timestamp(), updated_at=clock_timestamp()
            WHERE id=v_inbox.id;
            RETURN jsonb_build_object('result_code', 'ignored');
          END IF;
          v_payload_state := v_inbox.normalized_payload #>> '{subscription,state}';
          v_payload_currency := v_inbox.normalized_payload #>> '{subscription,currency}';
          v_period_start := (v_inbox.normalized_payload #>> '{subscription,current_period_start}')::timestamptz;
          v_period_end := (v_inbox.normalized_payload #>> '{subscription,current_period_end}')::timestamptz;
          v_provider_updated_at := (v_inbox.normalized_payload #>> '{subscription,updated_at}')::timestamptz;
          v_cancel_at_period_end := (v_inbox.normalized_payload #>> '{subscription,cancel_at_period_end}')::boolean;
          IF v_plan_version_state <> 'published'
             OR v_payload_currency IS NULL OR v_payload_currency <> (SELECT currency FROM public.subscriptions WHERE id=v_subscription_id)
             OR v_period_end <= v_period_start OR v_provider_updated_at IS NULL THEN
            UPDATE public.billing_event_inbox
            SET status='ignored', last_error_code='billing_payload_incompatible', processed_at=clock_timestamp(), updated_at=clock_timestamp()
            WHERE id=v_inbox.id;
            RETURN jsonb_build_object('result_code', 'ignored');
          END IF;
          -- A timestamp tie has no deterministic ordering in the normalized
          -- contract.  Treat it as ambiguous rather than letting arrival order
          -- overwrite a projection with an equally dated state.
          IF v_provider_updated_at <= (SELECT provider_updated_at FROM public.subscriptions WHERE id=v_subscription_id) THEN
            UPDATE public.billing_event_inbox
            SET status='ignored', last_error_code='billing_event_stale', processed_at=clock_timestamp(), updated_at=clock_timestamp()
            WHERE id=v_inbox.id;
            RETURN jsonb_build_object('result_code', 'ignored');
          END IF;
          v_next_state := v_current_state;
          v_cause := NULL;
          IF v_inbox.event_type = 'invoice.paid' THEN
            IF v_payload_state <> 'active' OR v_current_state NOT IN ('pending_checkout','active','past_due','grace_period','suspended') THEN
              UPDATE public.billing_event_inbox SET status='ignored', last_error_code='billing_transition_invalid', processed_at=clock_timestamp(), updated_at=clock_timestamp() WHERE id=v_inbox.id;
              RETURN jsonb_build_object('result_code', 'ignored');
            END IF;
            v_next_state := 'active'; v_cause := 'invoice_paid';
          ELSIF v_inbox.event_type = 'invoice.payment_failed' THEN
            IF v_payload_state <> 'past_due' OR v_current_state NOT IN ('active','past_due') THEN
              UPDATE public.billing_event_inbox SET status='ignored', last_error_code='billing_transition_invalid', processed_at=clock_timestamp(), updated_at=clock_timestamp() WHERE id=v_inbox.id;
              RETURN jsonb_build_object('result_code', 'ignored');
            END IF;
            v_next_state := 'past_due'; v_cause := 'payment_failed';
          ELSIF v_inbox.event_type = 'subscription.snapshot' AND v_payload_state <> v_current_state THEN
            UPDATE public.billing_event_inbox SET status='ignored', last_error_code='billing_transition_deferred', processed_at=clock_timestamp(), updated_at=clock_timestamp() WHERE id=v_inbox.id;
            RETURN jsonb_build_object('result_code', 'ignored');
          ELSIF v_inbox.event_type = 'checkout.completed' AND v_payload_state <> 'pending_checkout' THEN
            UPDATE public.billing_event_inbox SET status='ignored', last_error_code='billing_transition_invalid', processed_at=clock_timestamp(), updated_at=clock_timestamp() WHERE id=v_inbox.id;
            RETURN jsonb_build_object('result_code', 'ignored');
          END IF;
          UPDATE public.subscriptions
          SET state=v_next_state, current_period_start=v_period_start, current_period_end=v_period_end,
              cancel_at_period_end=v_cancel_at_period_end, provider_updated_at=v_provider_updated_at,
              provider_version=provider_version+1, version=version+1, updated_at=clock_timestamp()
          WHERE id=v_subscription_id;
          INSERT INTO public.billing_events(
            organization_id, inbox_id, subscription_id, provider, provider_event_id, event_type,
            schema_version, normalized_payload, occurred_at
          ) VALUES (
            v_organization_id, v_inbox.id, v_subscription_id, v_inbox.provider, v_inbox.provider_event_id,
            v_inbox.event_type, 1, v_inbox.normalized_payload, v_inbox.provider_created_at
          ) RETURNING id INTO v_billing_event_id;
          IF v_next_state <> v_current_state THEN
            INSERT INTO public.subscription_transitions(
              organization_id, subscription_id, source_billing_event_id, previous_state, next_state, cause, occurred_at
            ) VALUES (
              v_organization_id, v_subscription_id, v_billing_event_id, v_current_state, v_next_state,
              v_cause, v_inbox.provider_created_at
            );
            IF v_next_state='active' THEN
              UPDATE public.organization_plan_contracts
              SET state='active', updated_at=clock_timestamp(), version=version+1
              WHERE organization_id=v_organization_id AND plan_version_id=v_plan_version_id
                AND currency=v_payload_currency AND state='pending';
            END IF;
            v_request_id := 'billing-inbox-' || v_inbox.id::text;
            PERFORM set_config('app.organization_id', v_organization_id::text, true);
            PERFORM set_config('app.request_id', v_request_id, true);
            PERFORM app_private.append_audit_event(
              gen_random_uuid(), 'tenant', v_organization_id, 'system', NULL,
              'billing.subscription_transition_applied', 'subscription', v_subscription_id,
              v_request_id, v_request_id, 'worker',
              jsonb_build_object('event_type',v_inbox.event_type,'previous_state',v_current_state,'next_state',v_next_state),
              1::smallint
            );
          END IF;
          UPDATE public.billing_event_inbox
          SET status='processed', last_error_code=NULL, processed_at=clock_timestamp(), updated_at=clock_timestamp()
          WHERE id=v_inbox.id;
          RETURN jsonb_build_object('result_code', CASE WHEN v_next_state=v_current_state THEN 'processed' ELSE 'transitioned' END);
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.fail_billing_event_projection(p_inbox_id uuid)
        RETURNS text LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_attempts smallint;
        BEGIN
          SELECT attempt_count INTO v_attempts FROM public.billing_event_inbox
          WHERE id=p_inbox_id AND status='processing' FOR UPDATE;
          IF NOT FOUND THEN RETURN 'lost_claim'; END IF;
          IF v_attempts >= 8 THEN
            UPDATE public.billing_event_inbox SET status='dead_letter', last_error_code='projection_attempts_exhausted',
              processed_at=clock_timestamp(), updated_at=clock_timestamp() WHERE id=p_inbox_id;
            RETURN 'dead_letter';
          END IF;
          UPDATE public.billing_event_inbox SET status='admitted', last_error_code='projection_unavailable',
            next_attempt_at=clock_timestamp()
              + (LEAST(3600, 15 * (2 ^ (v_attempts - 1))) * interval '1 second')
              + (floor(random() * 15) * interval '1 second'),
            processing_started_at=NULL, updated_at=clock_timestamp() WHERE id=p_inbox_id;
          RETURN 'retry_scheduled';
        END $fn$;
        """
    )
    for signature in (_CLAIM_SIGNATURE, _PROJECT_SIGNATURE, _FAIL_SIGNATURE):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_worker")


def downgrade() -> None:
    for signature in (_FAIL_SIGNATURE, _PROJECT_SIGNATURE, _CLAIM_SIGNATURE):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM prospect_worker")
        op.execute(f"DROP FUNCTION {signature}")
