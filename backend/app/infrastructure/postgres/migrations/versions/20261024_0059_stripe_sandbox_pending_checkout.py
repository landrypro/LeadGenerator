"""Persistance et projection atomique de Checkout Stripe sandbox P53-09.

Revision ID: 20261024_0059
Revises: 20261023_0058
"""

from alembic import op

revision = "20261024_0059"
down_revision = "20261023_0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE TABLE public.stripe_sandbox_checkout_sessions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          billing_command_id uuid NOT NULL REFERENCES public.billing_commands(id) ON DELETE RESTRICT,
          billing_customer_id uuid NOT NULL REFERENCES public.billing_customers(id) ON DELETE RESTRICT,
          plan_version_id uuid NOT NULL REFERENCES public.plan_versions(id) ON DELETE RESTRICT,
          provider_checkout_reference varchar(255) NOT NULL,
          provider_price_reference varchar(255) NOT NULL,
          currency varchar(3) NOT NULL,
          expires_at timestamptz NOT NULL,
          completed_at timestamptz NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT uq_stripe_sandbox_checkout_command UNIQUE (billing_command_id),
          CONSTRAINT uq_stripe_sandbox_checkout_reference UNIQUE (provider_checkout_reference),
          CONSTRAINT ck_stripe_sandbox_checkout_currency CHECK (currency IN ('CAD','USD','EUR','XAF')),
          CONSTRAINT ck_stripe_sandbox_checkout_references CHECK (
            provider_checkout_reference ~ '^cs_test_[A-Za-z0-9_]+$'
            AND provider_price_reference ~ '^price_[A-Za-z0-9_]+$'
          )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_stripe_sandbox_checkout_pending
          ON public.stripe_sandbox_checkout_sessions(organization_id, completed_at)
          WHERE completed_at IS NULL
        """
    )
    op.execute("ALTER TABLE public.stripe_sandbox_checkout_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.stripe_sandbox_checkout_sessions FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON public.stripe_sandbox_checkout_sessions FROM PUBLIC, prospect_app, prospect_worker")
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.stripe_sandbox_checkout_sessions TO prospect_rls_definer")
    op.execute(
        r"""
        CREATE FUNCTION app_private.prepare_stripe_sandbox_checkout(
          p_command_id uuid, p_plan_version_id uuid, p_key_digest text,
          p_request_fingerprint text, p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_result jsonb; v_version public.plan_versions%ROWTYPE;
        BEGIN
          v_result:=app_private.prepare_billing_checkout(
            p_command_id,p_plan_version_id,p_key_digest,p_request_fingerprint,p_now
          );
          IF (v_result->>'code') NOT IN ('reserved','replayed') THEN RETURN v_result; END IF;
          SELECT * INTO v_version FROM public.plan_versions WHERE id=(v_result->>'plan_version_id')::uuid;
          IF NOT FOUND OR v_version.amount_excluding_tax_minor<=0 OR v_version.billing_cycle NOT IN ('monthly','annual') THEN
            RETURN jsonb_build_object('code','billing_catalog_version_unavailable');
          END IF;
          RETURN v_result || jsonb_build_object(
            'amount_minor',v_version.amount_excluding_tax_minor,'billing_cycle',v_version.billing_cycle
          );
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.complete_stripe_sandbox_checkout(
          p_command_id uuid, p_plan_version_id uuid, p_checkout_reference text,
          p_customer_reference text, p_price_reference text, p_currency text, p_expires_at timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_org uuid:=app_private.current_organization_id();
          v_actor uuid:=app_private.current_actor_id();
          v_command public.billing_commands%ROWTYPE;
          v_customer public.billing_customers%ROWTYPE;
          v_existing public.stripe_sandbox_checkout_sessions%ROWTYPE;
        BEGIN
          IF v_org IS NULL OR v_actor IS NULL OR p_command_id IS NULL OR p_plan_version_id IS NULL
             OR p_checkout_reference !~ '^cs_test_[A-Za-z0-9_]+$'
             OR p_customer_reference !~ '^cus_[A-Za-z0-9_]+$'
             OR p_price_reference !~ '^price_[A-Za-z0-9_]+$'
             OR p_currency NOT IN ('CAD','USD','EUR','XAF') OR p_expires_at <= clock_timestamp() THEN
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          SELECT * INTO v_command FROM public.billing_commands
          WHERE id=p_command_id AND organization_id=v_org AND command_kind='checkout' FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','billing_state_unknown'); END IF;
          IF v_command.status='unknown' THEN RETURN jsonb_build_object('code','billing_reconciliation_required'); END IF;
          IF v_command.request_fingerprint <> encode(sha256(convert_to('[' || chr(34) || 'checkout' || chr(34) || ',' || chr(34) || p_plan_version_id::text || chr(34) || ',' || chr(34) || 'subscription' || chr(34) || ']', 'UTF8')), 'hex')
             OR NOT EXISTS (SELECT 1 FROM public.plan_versions WHERE id=p_plan_version_id AND currency=p_currency) THEN
            RETURN jsonb_build_object('code','billing_catalog_version_unavailable');
          END IF;
          SELECT * INTO v_existing FROM public.stripe_sandbox_checkout_sessions
          WHERE billing_command_id=p_command_id FOR UPDATE;
          IF FOUND THEN
            IF v_existing.provider_checkout_reference=p_checkout_reference AND v_existing.provider_price_reference=p_price_reference THEN
              RETURN jsonb_build_object('code','replayed');
            END IF;
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          SELECT * INTO v_customer FROM public.billing_customers
          WHERE organization_id=v_org AND provider='stripe' FOR UPDATE;
          IF FOUND AND v_customer.provider_customer_reference<>p_customer_reference THEN
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          IF NOT FOUND THEN
            INSERT INTO public.billing_customers(organization_id,provider,provider_customer_reference)
            VALUES(v_org,'stripe',p_customer_reference) RETURNING * INTO v_customer;
          END IF;
          INSERT INTO public.stripe_sandbox_checkout_sessions(
            organization_id,billing_command_id,billing_customer_id,plan_version_id,provider_checkout_reference,
            provider_price_reference,currency,expires_at
          ) VALUES(v_org,p_command_id,v_customer.id,p_plan_version_id,p_checkout_reference,p_price_reference,p_currency,p_expires_at);
          UPDATE public.billing_commands SET status='succeeded',provider_command_reference=p_checkout_reference,
            updated_at=clock_timestamp(),version=version+1 WHERE id=p_command_id;
          RETURN jsonb_build_object('code','succeeded');
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.billing_event_provider(p_inbox_id uuid)
        RETURNS text LANGUAGE sql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
          SELECT provider FROM public.billing_event_inbox WHERE id=p_inbox_id AND status='processing'
        $fn$
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.project_stripe_sandbox_subscription_event(p_inbox_id uuid)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_inbox public.billing_event_inbox%ROWTYPE;
          v_checkout public.stripe_sandbox_checkout_sessions%ROWTYPE;
          v_subscription public.subscriptions%ROWTYPE;
          v_customer_reference text; v_price_reference text; v_subscription_reference text;
          v_currency text; v_state text; v_start timestamptz; v_end timestamptz; v_updated timestamptz; v_cancel boolean;
        BEGIN
          SELECT * INTO v_inbox FROM public.billing_event_inbox WHERE id=p_inbox_id FOR UPDATE;
          IF NOT FOUND OR v_inbox.status<>'processing' THEN RETURN jsonb_build_object('result_code','lost_claim'); END IF;
          IF v_inbox.provider<>'stripe' OR v_inbox.event_type<>'subscription.snapshot'
             OR (v_inbox.normalized_payload->>'checkout_command_id') !~ '^[0-9a-f-]{36}$' THEN
            UPDATE public.billing_event_inbox SET status='ignored',last_error_code='stripe_mapping_missing',processed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=p_inbox_id;
            RETURN jsonb_build_object('result_code','ignored');
          END IF;
          SELECT * INTO v_checkout FROM public.stripe_sandbox_checkout_sessions
          WHERE billing_command_id=(v_inbox.normalized_payload->>'checkout_command_id')::uuid FOR UPDATE;
          v_customer_reference:=v_inbox.normalized_payload #>> '{subscription,customer_reference}';
          v_price_reference:=v_inbox.normalized_payload #>> '{subscription,price_reference}';
          v_subscription_reference:=v_inbox.normalized_payload #>> '{subscription,reference}';
          v_currency:=v_inbox.normalized_payload #>> '{subscription,currency}';
          v_state:=v_inbox.normalized_payload #>> '{subscription,state}';
          v_start:=(v_inbox.normalized_payload #>> '{subscription,current_period_start}')::timestamptz;
          v_end:=(v_inbox.normalized_payload #>> '{subscription,current_period_end}')::timestamptz;
          v_updated:=(v_inbox.normalized_payload #>> '{subscription,updated_at}')::timestamptz;
          v_cancel:=(v_inbox.normalized_payload #>> '{subscription,cancel_at_period_end}')::boolean;
          IF v_checkout.id IS NULL OR v_checkout.completed_at IS NOT NULL OR v_subscription_reference !~ '^sub_[A-Za-z0-9_]+$'
             OR v_customer_reference IS NULL OR v_price_reference<>v_checkout.provider_price_reference
             OR v_currency<>v_checkout.currency OR v_state NOT IN ('pending_checkout','active','past_due','suspended','canceling','canceled')
             OR v_start IS NULL OR v_end<=v_start OR v_updated IS NULL OR v_cancel IS NULL
             OR NOT EXISTS (SELECT 1 FROM public.billing_customers WHERE id=v_checkout.billing_customer_id AND provider='stripe' AND provider_customer_reference=v_customer_reference) THEN
            UPDATE public.billing_event_inbox SET status='ignored',last_error_code='stripe_mapping_incompatible',processed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=p_inbox_id;
            RETURN jsonb_build_object('result_code','ignored');
          END IF;
          SELECT * INTO v_subscription FROM public.subscriptions WHERE provider='stripe' AND provider_subscription_reference=v_subscription_reference FOR UPDATE;
          IF FOUND AND (v_subscription.organization_id<>v_checkout.organization_id OR v_subscription.billing_customer_id<>v_checkout.billing_customer_id OR v_subscription.plan_version_id<>v_checkout.plan_version_id OR v_subscription.currency<>v_checkout.currency) THEN
            UPDATE public.billing_event_inbox SET status='ignored',last_error_code='stripe_subscription_conflict',processed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=p_inbox_id;
            RETURN jsonb_build_object('result_code','ignored');
          END IF;
          IF NOT FOUND THEN
            INSERT INTO public.subscriptions(organization_id,billing_customer_id,provider,provider_subscription_reference,plan_version_id,currency,state,current_period_start,current_period_end,cancel_at_period_end,provider_updated_at)
            VALUES(v_checkout.organization_id,v_checkout.billing_customer_id,'stripe',v_subscription_reference,v_checkout.plan_version_id,v_checkout.currency,v_state,v_start,v_end,v_cancel,v_updated)
            RETURNING * INTO v_subscription;
          ELSIF v_updated > v_subscription.provider_updated_at THEN
            UPDATE public.subscriptions SET state=v_state,current_period_start=v_start,current_period_end=v_end,cancel_at_period_end=v_cancel,provider_updated_at=v_updated,provider_version=provider_version+1,version=version+1,updated_at=clock_timestamp() WHERE id=v_subscription.id RETURNING * INTO v_subscription;
          END IF;
          UPDATE public.stripe_sandbox_checkout_sessions SET completed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=v_checkout.id;
          INSERT INTO public.billing_events(organization_id,inbox_id,subscription_id,provider,provider_event_id,event_type,schema_version,normalized_payload,occurred_at)
          VALUES(v_checkout.organization_id,v_inbox.id,v_subscription.id,'stripe',v_inbox.provider_event_id,v_inbox.event_type,1,v_inbox.normalized_payload,v_inbox.provider_created_at);
          IF v_state='active' THEN UPDATE public.organization_plan_contracts SET state='active',updated_at=clock_timestamp(),version=version+1 WHERE organization_id=v_checkout.organization_id AND plan_version_id=v_checkout.plan_version_id AND currency=v_checkout.currency AND state='pending'; END IF;
          UPDATE public.billing_event_inbox SET status='processed',last_error_code=NULL,processed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=p_inbox_id;
          RETURN jsonb_build_object('result_code','processed');
        END $fn$
        """
    )
    for signature in (
        "app_private.prepare_stripe_sandbox_checkout(uuid,uuid,text,text,timestamptz)",
        "app_private.complete_stripe_sandbox_checkout(uuid,uuid,text,text,text,text,timestamptz)",
        "app_private.billing_event_provider(uuid)",
        "app_private.project_stripe_sandbox_subscription_event(uuid)",
    ):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_worker")
    op.execute(
        "REVOKE EXECUTE ON FUNCTION app_private.prepare_stripe_sandbox_checkout(uuid,uuid,text,text,timestamptz) FROM prospect_worker"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_private.prepare_stripe_sandbox_checkout(uuid,uuid,text,text,timestamptz) TO prospect_app"
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION app_private.complete_stripe_sandbox_checkout(uuid,uuid,text,text,text,text,timestamptz) FROM prospect_worker"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_private.complete_stripe_sandbox_checkout(uuid,uuid,text,text,text,text,timestamptz) TO prospect_app"
    )


def downgrade() -> None:
    for signature in (
        "app_private.project_stripe_sandbox_subscription_event(uuid)",
        "app_private.billing_event_provider(uuid)",
        "app_private.complete_stripe_sandbox_checkout(uuid,uuid,text,text,text,text,timestamptz)",
        "app_private.prepare_stripe_sandbox_checkout(uuid,uuid,text,text,timestamptz)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM prospect_app, prospect_worker")
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE public.stripe_sandbox_checkout_sessions")
