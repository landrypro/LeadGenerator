"""Grâce, annulation et remboursement simulé P53-07.

Revision ID: 20261010_0055
Revises: 20261010_0054
Create Date: 2026-10-10
"""

from alembic import op

revision = "20261010_0055"
down_revision = "20261010_0054"
branch_labels = None
depends_on = None

_CLAIM_TIMER = "app_private.claim_billing_lifecycle_timer()"
_PROJECT_TIMER = "app_private.project_billing_lifecycle_timer(uuid)"
_PROJECT_EVENT = "app_private.project_billing_event(uuid)"
_PREPARE_REFUND = "app_private.prepare_platform_billing_refund(uuid,uuid,uuid,text,text,timestamptz)"
_COMPLETE_REFUND = "app_private.complete_platform_billing_refund(uuid,text)"
_MARK_REFUND = "app_private.mark_platform_billing_refund(uuid,text)"


def upgrade() -> None:
    op.execute("ALTER TABLE public.subscriptions ADD COLUMN grace_policy_version smallint NULL")
    op.execute("ALTER TABLE public.subscriptions ADD COLUMN grace_started_at timestamptz NULL")
    op.execute("ALTER TABLE public.subscriptions ADD COLUMN grace_ends_at timestamptz NULL")
    op.execute(
        """
        ALTER TABLE public.subscriptions ADD CONSTRAINT ck_subscriptions_grace_window CHECK (
          (grace_policy_version IS NULL AND grace_started_at IS NULL AND grace_ends_at IS NULL)
          OR (grace_policy_version = 1 AND grace_started_at IS NOT NULL AND grace_ends_at = grace_started_at + interval '7 days')
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_subscriptions_grace_due ON public.subscriptions(grace_ends_at) WHERE state='grace_period'"
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.claim_billing_lifecycle_timer()
        RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_id uuid;
        BEGIN
          SELECT id INTO v_id FROM public.subscriptions
          WHERE (state='past_due' AND grace_started_at IS NULL)
             OR (state='grace_period' AND grace_ends_at <= clock_timestamp())
          ORDER BY COALESCE(grace_ends_at, provider_updated_at), id
          FOR UPDATE SKIP LOCKED LIMIT 1;
          RETURN v_id;
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.prepare_platform_billing_refund(
          p_command_id uuid,p_organization_id uuid,p_subscription_id uuid,p_key_digest text,p_request_fingerprint text,p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_existing public.billing_commands%ROWTYPE;
          v_subscription public.subscriptions%ROWTYPE; v_payment_reference text; v_refund public.billing_refunds%ROWTYPE; v_request text:=current_setting('app.request_id',true);
        BEGIN
          IF v_actor IS NULL OR p_command_id IS NULL OR p_organization_id IS NULL OR p_subscription_id IS NULL OR p_now IS NULL
            OR p_key_digest !~ '^[a-f0-9]{64}$' OR p_request_fingerprint !~ '^[a-f0-9]{64}$' THEN RETURN jsonb_build_object('code','billing_refund_not_eligible'); END IF;
          IF NOT EXISTS(SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin') THEN RETURN jsonb_build_object('code','billing_capability_required'); END IF;
          SELECT * INTO v_existing FROM public.billing_commands WHERE organization_id=p_organization_id AND idempotency_key_digest=p_key_digest FOR UPDATE;
          IF FOUND THEN
            IF v_existing.command_kind<>'refund' OR v_existing.request_fingerprint<>p_request_fingerprint THEN RETURN jsonb_build_object('code','billing_command_conflict'); END IF;
            SELECT * INTO v_refund FROM public.billing_refunds WHERE billing_command_id=v_existing.id;
            RETURN jsonb_build_object('code','replayed','command_id',v_existing.id,'status',v_existing.status,'refund_id',v_refund.id,'payment_reference',v_refund.provider_payment_reference);
          END IF;
          SELECT * INTO v_subscription FROM public.subscriptions WHERE id=p_subscription_id AND organization_id=p_organization_id AND provider='simulated' FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','billing_refund_not_eligible'); END IF;
          SELECT provider_event_id INTO v_payment_reference FROM public.billing_events WHERE organization_id=p_organization_id AND subscription_id=p_subscription_id AND event_type='invoice.paid' ORDER BY occurred_at,id LIMIT 1;
          IF v_payment_reference IS NULL OR p_now > (SELECT occurred_at + interval '14 days' FROM public.billing_events WHERE organization_id=p_organization_id AND subscription_id=p_subscription_id AND event_type='invoice.paid' ORDER BY occurred_at,id LIMIT 1)
            OR EXISTS(SELECT 1 FROM public.billing_refunds WHERE organization_id=p_organization_id AND subscription_id=p_subscription_id AND state IN ('requested','approved','succeeded')) THEN
            RETURN jsonb_build_object('code','billing_refund_not_eligible');
          END IF;
          INSERT INTO public.billing_commands(id,organization_id,command_kind,idempotency_key_digest,request_fingerprint,status,created_at,updated_at)
          VALUES(p_command_id,p_organization_id,'refund',p_key_digest,p_request_fingerprint,'reserved',p_now,p_now);
          INSERT INTO public.billing_refunds(organization_id,subscription_id,billing_command_id,provider_payment_reference,state,requested_at,decided_at)
          VALUES(p_organization_id,p_subscription_id,p_command_id,v_payment_reference,'approved',p_now,p_now) RETURNING * INTO v_refund;
          PERFORM app_private.append_audit_event(gen_random_uuid(),'platform',NULL,'user',v_actor,'billing.refund_requested','billing_refund',v_refund.id,v_request,v_request,'api',jsonb_build_object('state','requested'),1::smallint);
          PERFORM app_private.append_audit_event(gen_random_uuid(),'platform',NULL,'user',v_actor,'billing.refund_approved','billing_refund',v_refund.id,v_request,v_request,'api',jsonb_build_object('state','approved'),1::smallint);
          RETURN jsonb_build_object('code','reserved','command_id',p_command_id,'status','reserved','refund_id',v_refund.id,'payment_reference',v_payment_reference);
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.complete_platform_billing_refund(p_command_id uuid,p_provider_event_id text)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_command public.billing_commands%ROWTYPE;
        BEGIN
          SELECT * INTO v_command FROM public.billing_commands WHERE id=p_command_id AND command_kind='refund' FOR UPDATE;
          IF NOT FOUND OR p_provider_event_id IS NULL OR btrim(p_provider_event_id)='' THEN RETURN jsonb_build_object('code','billing_state_unknown'); END IF;
          IF NOT EXISTS(SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin') THEN RETURN jsonb_build_object('code','billing_capability_required'); END IF;
          IF v_command.status='unknown' THEN RETURN jsonb_build_object('code','billing_reconciliation_required'); END IF;
          IF v_command.status='succeeded' THEN RETURN jsonb_build_object('code','replayed'); END IF;
          UPDATE public.billing_commands SET status='succeeded',provider_command_reference=p_provider_event_id,updated_at=clock_timestamp(),version=version+1 WHERE id=v_command.id;
          RETURN jsonb_build_object('code','succeeded');
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.mark_platform_billing_refund(p_command_id uuid,p_status text)
        RETURNS text LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_command public.billing_commands%ROWTYPE;
        BEGIN
          IF p_status NOT IN ('failed','unknown') OR NOT EXISTS(SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin') THEN RETURN 'forbidden'; END IF;
          UPDATE public.billing_commands SET status=p_status,updated_at=clock_timestamp(),version=version+1 WHERE id=p_command_id AND command_kind='refund' AND status IN ('reserved','failed') RETURNING * INTO v_command;
          IF FOUND AND p_status='failed' THEN UPDATE public.billing_refunds SET state='failed',updated_at=clock_timestamp(),version=version+1 WHERE billing_command_id=v_command.id; END IF;
          RETURN CASE WHEN FOUND THEN p_status ELSE 'unchanged' END;
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.project_billing_lifecycle_timer(p_subscription_id uuid)
        RETURNS text LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_subscription public.subscriptions%ROWTYPE;
          v_request text;
        BEGIN
          SELECT * INTO v_subscription FROM public.subscriptions WHERE id=p_subscription_id FOR UPDATE;
          IF NOT FOUND THEN RETURN 'lost_claim'; END IF;
          v_request := 'billing-timer-' || v_subscription.id::text;
          IF v_subscription.state='past_due' AND v_subscription.grace_started_at IS NULL THEN
            UPDATE public.subscriptions SET state='grace_period',grace_policy_version=1,
              grace_started_at=clock_timestamp(),grace_ends_at=clock_timestamp()+interval '7 days',
              updated_at=clock_timestamp(),version=version+1 WHERE id=v_subscription.id;
            INSERT INTO public.subscription_transitions(organization_id,subscription_id,source_billing_event_id,previous_state,next_state,cause,occurred_at)
            VALUES(v_subscription.organization_id,v_subscription.id,NULL,'past_due','grace_period','grace_period_started',clock_timestamp());
            PERFORM set_config('app.organization_id',v_subscription.organization_id::text,true);
            PERFORM set_config('app.request_id',v_request,true);
            PERFORM app_private.append_audit_event(gen_random_uuid(),'tenant',v_subscription.organization_id,'system',NULL,
              'billing.grace_started','subscription',v_subscription.id,v_request,v_request,'worker',
              jsonb_build_object('previous_state','past_due','next_state','grace_period'),1::smallint);
            RETURN 'grace_started';
          END IF;
          IF v_subscription.state='grace_period' AND v_subscription.grace_ends_at <= clock_timestamp() THEN
            UPDATE public.subscriptions SET state='suspended',updated_at=clock_timestamp(),version=version+1 WHERE id=v_subscription.id;
            UPDATE public.organization_plan_contracts SET state='suspended',updated_at=clock_timestamp(),version=version+1
              WHERE organization_id=v_subscription.organization_id AND plan_version_id=v_subscription.plan_version_id AND state='active';
            INSERT INTO public.subscription_transitions(organization_id,subscription_id,source_billing_event_id,previous_state,next_state,cause,occurred_at)
            VALUES(v_subscription.organization_id,v_subscription.id,NULL,'grace_period','suspended','grace_period_expired',clock_timestamp());
            PERFORM set_config('app.organization_id',v_subscription.organization_id::text,true);
            PERFORM set_config('app.request_id',v_request,true);
            PERFORM app_private.append_audit_event(gen_random_uuid(),'tenant',v_subscription.organization_id,'system',NULL,
              'billing.grace_expired','subscription',v_subscription.id,v_request,v_request,'worker',
              jsonb_build_object('previous_state','grace_period','next_state','suspended'),1::smallint);
            RETURN 'suspended';
          END IF;
          RETURN 'unchanged';
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.project_billing_event(p_inbox_id uuid)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_inbox public.billing_event_inbox%ROWTYPE; v_subscription public.subscriptions%ROWTYPE;
          v_plan_state text; v_payload_state text; v_payload_currency text; v_period_start timestamptz;
          v_period_end timestamptz; v_provider_updated_at timestamptz; v_cancel_at_period_end boolean;
          v_next_state text; v_cause text; v_billing_event_id uuid; v_request_id text; v_action text;
          v_refund public.billing_refunds%ROWTYPE;
        BEGIN
          SELECT * INTO v_inbox FROM public.billing_event_inbox WHERE id=p_inbox_id FOR UPDATE;
          IF NOT FOUND OR v_inbox.status<>'processing' THEN RETURN jsonb_build_object('result_code','lost_claim'); END IF;
          IF v_inbox.event_type='refund.succeeded' THEN
            SELECT r.* INTO v_refund FROM public.billing_refunds r
            JOIN public.subscriptions s ON s.id=r.subscription_id AND s.organization_id=r.organization_id
            WHERE s.provider=v_inbox.provider AND r.provider_payment_reference=v_inbox.provider_object_reference
              AND r.state='approved' FOR UPDATE OF r;
            IF NOT FOUND THEN
              UPDATE public.billing_event_inbox SET status='ignored',last_error_code='billing_refund_mapping_missing',processed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=v_inbox.id;
              RETURN jsonb_build_object('result_code','ignored');
            END IF;
            UPDATE public.billing_refunds SET state='succeeded',provider_refund_reference=v_inbox.provider_event_id,
              completed_at=clock_timestamp(),updated_at=clock_timestamp(),version=version+1 WHERE id=v_refund.id;
            INSERT INTO public.billing_events(organization_id,inbox_id,subscription_id,provider,provider_event_id,event_type,schema_version,normalized_payload,occurred_at)
            VALUES(v_refund.organization_id,v_inbox.id,v_refund.subscription_id,v_inbox.provider,v_inbox.provider_event_id,v_inbox.event_type,1,v_inbox.normalized_payload,v_inbox.provider_created_at);
            v_request_id := 'billing-inbox-' || v_inbox.id::text; PERFORM set_config('app.organization_id','',true); PERFORM set_config('app.request_id',v_request_id,true);
            PERFORM app_private.append_audit_event(gen_random_uuid(),'platform',NULL,'system',NULL,'billing.refund_confirmed','billing_refund',v_refund.id,v_request_id,v_request_id,'worker',jsonb_build_object('state','succeeded'),1::smallint);
            UPDATE public.billing_event_inbox SET status='processed',processed_at=clock_timestamp(),updated_at=clock_timestamp(),last_error_code=NULL WHERE id=v_inbox.id;
            RETURN jsonb_build_object('result_code','processed');
          END IF;
          SELECT s.* INTO v_subscription FROM public.subscriptions s JOIN public.billing_customers c ON c.id=s.billing_customer_id AND c.organization_id=s.organization_id
          WHERE s.provider=v_inbox.provider AND s.provider_subscription_reference=(v_inbox.normalized_payload #>> '{subscription,reference}')
            AND c.provider_customer_reference=(v_inbox.normalized_payload #>> '{subscription,customer_reference}') FOR UPDATE OF s;
          IF NOT FOUND THEN UPDATE public.billing_event_inbox SET status='ignored',last_error_code='billing_mapping_missing',processed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=v_inbox.id; RETURN jsonb_build_object('result_code','ignored'); END IF;
          SELECT state INTO v_plan_state FROM public.plan_versions WHERE id=v_subscription.plan_version_id;
          v_payload_state:=v_inbox.normalized_payload #>> '{subscription,state}'; v_payload_currency:=v_inbox.normalized_payload #>> '{subscription,currency}';
          v_period_start:=(v_inbox.normalized_payload #>> '{subscription,current_period_start}')::timestamptz; v_period_end:=(v_inbox.normalized_payload #>> '{subscription,current_period_end}')::timestamptz;
          v_provider_updated_at:=(v_inbox.normalized_payload #>> '{subscription,updated_at}')::timestamptz; v_cancel_at_period_end:=(v_inbox.normalized_payload #>> '{subscription,cancel_at_period_end}')::boolean;
          IF v_plan_state<>'published' OR v_payload_currency<>v_subscription.currency OR v_period_end<=v_period_start OR v_provider_updated_at IS NULL THEN
            UPDATE public.billing_event_inbox SET status='ignored',last_error_code='billing_payload_incompatible',processed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=v_inbox.id; RETURN jsonb_build_object('result_code','ignored'); END IF;
          IF v_provider_updated_at<=v_subscription.provider_updated_at THEN UPDATE public.billing_event_inbox SET status='ignored',last_error_code='billing_event_stale',processed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=v_inbox.id; RETURN jsonb_build_object('result_code','ignored'); END IF;
          v_next_state:=v_subscription.state; v_cause:=NULL; v_action:=NULL;
          IF v_inbox.event_type='invoice.paid' AND v_payload_state='active' AND v_subscription.state IN ('pending_checkout','active','past_due','grace_period','suspended') THEN v_next_state:='active';v_cause:='invoice_paid';
          ELSIF v_inbox.event_type='invoice.payment_failed' AND v_payload_state='past_due' AND v_subscription.state IN ('active','past_due') THEN v_next_state:='past_due';v_cause:='payment_failed';
          ELSIF v_inbox.event_type='subscription.snapshot' AND v_payload_state='canceling' AND v_subscription.state IN ('active','past_due') THEN v_next_state:='canceling';v_cause:='cancellation_scheduled';v_action:='billing.cancellation_scheduled';
          ELSIF v_inbox.event_type='subscription.snapshot' AND v_payload_state='active' AND v_subscription.state='canceling' THEN v_next_state:='active';v_cause:='cancellation_revoked';v_action:='billing.cancellation_revoked';
          ELSIF v_inbox.event_type='subscription.snapshot' AND v_payload_state='canceled' AND v_subscription.state='canceling' THEN v_next_state:='canceled';v_cause:='cancellation_confirmed';v_action:='billing.cancellation_confirmed';
          ELSIF v_inbox.event_type='checkout.completed' AND v_payload_state='pending_checkout' THEN NULL;
          ELSIF v_inbox.event_type='subscription.snapshot' AND v_payload_state=v_subscription.state THEN NULL;
          ELSE UPDATE public.billing_event_inbox SET status='ignored',last_error_code='billing_transition_deferred',processed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=v_inbox.id; RETURN jsonb_build_object('result_code','ignored'); END IF;
          UPDATE public.subscriptions SET state=v_next_state,current_period_start=v_period_start,current_period_end=v_period_end,cancel_at_period_end=v_cancel_at_period_end,provider_updated_at=v_provider_updated_at,provider_version=provider_version+1,version=version+1,updated_at=clock_timestamp(),
            grace_policy_version=CASE WHEN v_next_state='active' THEN NULL ELSE grace_policy_version END,grace_started_at=CASE WHEN v_next_state='active' THEN NULL ELSE grace_started_at END,grace_ends_at=CASE WHEN v_next_state='active' THEN NULL ELSE grace_ends_at END WHERE id=v_subscription.id;
          INSERT INTO public.billing_events(organization_id,inbox_id,subscription_id,provider,provider_event_id,event_type,schema_version,normalized_payload,occurred_at)
          VALUES(v_subscription.organization_id,v_inbox.id,v_subscription.id,v_inbox.provider,v_inbox.provider_event_id,v_inbox.event_type,1,v_inbox.normalized_payload,v_inbox.provider_created_at) RETURNING id INTO v_billing_event_id;
          IF v_next_state<>v_subscription.state THEN
            INSERT INTO public.subscription_transitions(organization_id,subscription_id,source_billing_event_id,previous_state,next_state,cause,occurred_at) VALUES(v_subscription.organization_id,v_subscription.id,v_billing_event_id,v_subscription.state,v_next_state,v_cause,v_inbox.provider_created_at);
            IF v_next_state='active' THEN UPDATE public.organization_plan_contracts SET state='active',updated_at=clock_timestamp(),version=version+1 WHERE organization_id=v_subscription.organization_id AND plan_version_id=v_subscription.plan_version_id AND state IN ('pending','suspended');
            ELSIF v_next_state='canceled' THEN UPDATE public.organization_plan_contracts SET state='ended',updated_at=clock_timestamp(),version=version+1 WHERE organization_id=v_subscription.organization_id AND plan_version_id=v_subscription.plan_version_id AND state IN ('active','suspended'); END IF;
            v_request_id:='billing-inbox-'||v_inbox.id::text; PERFORM set_config('app.organization_id',v_subscription.organization_id::text,true); PERFORM set_config('app.request_id',v_request_id,true);
            PERFORM app_private.append_audit_event(gen_random_uuid(),'tenant',v_subscription.organization_id,'system',NULL,'billing.subscription_transition_applied','subscription',v_subscription.id,v_request_id,v_request_id,'worker',jsonb_build_object('event_type',v_inbox.event_type,'previous_state',v_subscription.state,'next_state',v_next_state),1::smallint);
            IF v_action IS NOT NULL THEN PERFORM app_private.append_audit_event(gen_random_uuid(),'tenant',v_subscription.organization_id,'system',NULL,v_action,'subscription',v_subscription.id,v_request_id,v_request_id,'worker',jsonb_build_object('previous_state',v_subscription.state,'next_state',v_next_state),1::smallint); END IF;
          END IF;
          UPDATE public.billing_event_inbox SET status='processed',last_error_code=NULL,processed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=v_inbox.id;
          RETURN jsonb_build_object('result_code',CASE WHEN v_next_state=v_subscription.state THEN 'processed' ELSE 'transitioned' END);
        END $fn$;
        """
    )
    for signature in (_CLAIM_TIMER, _PROJECT_TIMER, _PROJECT_EVENT):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_worker")
    for signature in (_PREPARE_REFUND, _COMPLETE_REFUND, _MARK_REFUND):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")


def downgrade() -> None:
    for signature in (_MARK_REFUND, _COMPLETE_REFUND, _PREPARE_REFUND):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM prospect_app")
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("REVOKE EXECUTE ON FUNCTION app_private.claim_billing_lifecycle_timer() FROM prospect_worker")
    op.execute("REVOKE EXECUTE ON FUNCTION app_private.project_billing_lifecycle_timer(uuid) FROM prospect_worker")
    op.execute("DROP FUNCTION app_private.claim_billing_lifecycle_timer()")
    op.execute("DROP FUNCTION app_private.project_billing_lifecycle_timer(uuid)")
    op.execute("DROP INDEX public.ix_subscriptions_grace_due")
    op.execute("ALTER TABLE public.subscriptions DROP CONSTRAINT ck_subscriptions_grace_window")
    op.execute("ALTER TABLE public.subscriptions DROP COLUMN grace_ends_at")
    op.execute("ALTER TABLE public.subscriptions DROP COLUMN grace_started_at")
    op.execute("ALTER TABLE public.subscriptions DROP COLUMN grace_policy_version")
