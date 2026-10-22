"""Checkout simulé multidevise P53-06B.

Revision ID: 20261021_0056
Revises: 20261010_0055
"""

from alembic import op

revision = "20261021_0056"
down_revision = "20261010_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.prepare_billing_checkout(
          p_command_id uuid, p_plan_version_id uuid, p_key_digest text,
          p_request_fingerprint text, p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_org uuid:=app_private.current_organization_id();
          v_actor uuid:=app_private.current_actor_id();
          v_request text:=current_setting('app.request_id',true);
          v_existing public.billing_commands%ROWTYPE;
          v_version public.plan_versions%ROWTYPE;
          v_plan_state text;
          v_active_limit bigint;
          v_pending_limit bigint;
          v_active_count bigint;
          v_pending_count bigint;
          v_price_reference text;
        BEGIN
          IF v_org IS NULL OR v_actor IS NULL OR p_command_id IS NULL OR p_plan_version_id IS NULL OR p_now IS NULL
             OR p_key_digest !~ '^[a-f0-9]{64}$' OR p_request_fingerprint !~ '^[a-f0-9]{64}$' THEN
            RETURN jsonb_build_object('code','billing_catalog_version_unavailable');
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.memberships m JOIN public.organizations o ON o.id=m.organization_id
            WHERE m.organization_id=v_org AND m.user_id=v_actor AND m.status='active'
              AND m.role='admin' AND o.status='active'
          ) THEN RETURN jsonb_build_object('code','billing_capability_required'); END IF;

          IF p_request_fingerprint <> encode(sha256(convert_to('["checkout","' || p_plan_version_id::text || '","subscription"]', 'UTF8')), 'hex') THEN
            RETURN jsonb_build_object('code','billing_command_conflict');
          END IF;

          SELECT * INTO v_existing FROM public.billing_commands
          WHERE organization_id=v_org AND idempotency_key_digest=p_key_digest FOR UPDATE;
          IF FOUND THEN
            IF v_existing.command_kind<>'checkout' OR v_existing.request_fingerprint<>p_request_fingerprint THEN
              RETURN jsonb_build_object('code','billing_command_conflict');
            END IF;
          END IF;

          SELECT * INTO v_version FROM public.plan_versions WHERE id=p_plan_version_id;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','billing_catalog_version_unavailable'); END IF;
          SELECT state INTO v_plan_state FROM public.plan_catalog WHERE id=v_version.plan_id;
          IF v_existing.id IS NULL AND (
             v_version.state<>'published' OR v_plan_state<>'published'
             OR v_version.effective_from>p_now
             OR (v_version.effective_until IS NOT NULL AND v_version.effective_until<=p_now)
          ) THEN
            RETURN jsonb_build_object('code','billing_catalog_version_unavailable');
          END IF;
          IF v_version.currency NOT IN ('CAD','USD','EUR','XAF') THEN
            RETURN jsonb_build_object('code','billing_currency_unavailable');
          END IF;

          SELECT integer_value INTO v_active_limit FROM public.plan_entitlements
          WHERE plan_version_id=p_plan_version_id AND entitlement_key='seats.active_members.max' AND value_kind='limit';
          SELECT integer_value INTO v_pending_limit FROM public.plan_entitlements
          WHERE plan_version_id=p_plan_version_id AND entitlement_key='seats.pending_invitations.max' AND value_kind='limit';
          IF v_active_limit IS NULL OR v_pending_limit IS NULL THEN
            RETURN jsonb_build_object('code','billing_catalog_version_unavailable');
          END IF;
          SELECT count(*) INTO v_active_count FROM public.memberships
          WHERE organization_id=v_org AND status='active';
          SELECT count(*) INTO v_pending_count FROM public.user_invitations
          WHERE organization_id=v_org AND invitation_kind='member' AND accepted_at IS NULL
            AND revoked_at IS NULL AND expires_at>p_now;
          IF v_existing.id IS NULL
             AND (v_active_count+v_pending_count>v_active_limit OR v_pending_count>v_pending_limit) THEN
            RETURN jsonb_build_object('code','billing_seat_limit_conflict');
          END IF;

          v_price_reference:='sim_price_' || replace(p_plan_version_id::text,'-','');
          IF v_existing.id IS NOT NULL THEN
            RETURN jsonb_build_object(
              'code','replayed','command_id',v_existing.id,'status',v_existing.status,
              'plan_version_id',p_plan_version_id,'currency',v_version.currency,
              'provider_price_reference',v_price_reference
            );
          END IF;
          IF EXISTS (
            SELECT 1 FROM public.subscriptions WHERE organization_id=v_org
              AND state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling')
          ) THEN RETURN jsonb_build_object('code','billing_subscription_exists'); END IF;

          INSERT INTO public.billing_commands(
            id,organization_id,command_kind,idempotency_key_digest,request_fingerprint,status,created_at,updated_at
          ) VALUES (p_command_id,v_org,'checkout',p_key_digest,p_request_fingerprint,'reserved',p_now,p_now)
          ON CONFLICT (organization_id,idempotency_key_digest) DO NOTHING;
          IF NOT FOUND THEN
            SELECT * INTO v_existing FROM public.billing_commands
            WHERE organization_id=v_org AND idempotency_key_digest=p_key_digest FOR UPDATE;
            IF v_existing.command_kind<>'checkout' OR v_existing.request_fingerprint<>p_request_fingerprint THEN
              RETURN jsonb_build_object('code','billing_command_conflict');
            END IF;
            RETURN jsonb_build_object(
              'code','replayed','command_id',v_existing.id,'status',v_existing.status,
              'plan_version_id',p_plan_version_id,'currency',v_version.currency,
              'provider_price_reference',v_price_reference
            );
          END IF;
          PERFORM app_private.append_audit_event(
            gen_random_uuid(),'tenant',v_org,'user',v_actor,'billing.checkout_requested',
            'billing_command',p_command_id,v_request,v_request,'api',
            jsonb_build_object('command_kind','checkout','replayed',false),1::smallint
          );
          RETURN jsonb_build_object(
            'code','reserved','command_id',p_command_id,'status','reserved',
            'plan_version_id',p_plan_version_id,'currency',v_version.currency,
            'provider_price_reference',v_price_reference
          );
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.complete_billing_checkout(
          p_command_id uuid, p_plan_version_id uuid, p_provider text, p_checkout_reference text,
          p_customer_reference text, p_subscription_reference text, p_currency text, p_price_reference text,
          p_period_start timestamptz, p_period_end timestamptz, p_provider_updated_at timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_org uuid:=app_private.current_organization_id();
          v_actor uuid:=app_private.current_actor_id();
          v_request text:=current_setting('app.request_id',true);
          v_command public.billing_commands%ROWTYPE;
          v_customer public.billing_customers%ROWTYPE;
          v_subscription public.subscriptions%ROWTYPE;
          v_expected_price text;
        BEGIN
          SELECT * INTO v_command FROM public.billing_commands
          WHERE id=p_command_id AND organization_id=v_org AND command_kind='checkout' FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','billing_state_unknown'); END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.memberships m JOIN public.organizations o ON o.id=m.organization_id
            WHERE m.organization_id=v_org AND m.user_id=v_actor AND m.status='active'
              AND m.role='admin' AND o.status='active'
          ) THEN RETURN jsonb_build_object('code','billing_capability_required'); END IF;
          IF p_plan_version_id IS NULL OR v_command.request_fingerprint <> encode(sha256(convert_to('["checkout","' || p_plan_version_id::text || '","subscription"]', 'UTF8')), 'hex') THEN
            RETURN jsonb_build_object('code','billing_command_conflict');
          END IF;
          IF v_command.status='unknown' THEN RETURN jsonb_build_object('code','billing_reconciliation_required'); END IF;
          IF p_provider<>'simulated' OR p_checkout_reference IS NULL OR btrim(p_checkout_reference)=''
             OR p_customer_reference IS NULL OR btrim(p_customer_reference)=''
             OR p_subscription_reference IS NULL OR btrim(p_subscription_reference)=''
             OR p_currency IS NULL OR p_currency NOT IN ('CAD','USD','EUR','XAF') OR p_period_start IS NULL OR p_period_end<=p_period_start
             OR p_provider_updated_at IS NULL THEN
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          v_expected_price:='sim_price_' || replace(p_plan_version_id::text,'-','');
          IF p_price_reference IS DISTINCT FROM v_expected_price OR NOT EXISTS (
            SELECT 1 FROM public.plan_versions WHERE id=p_plan_version_id AND currency=p_currency
          ) THEN RETURN jsonb_build_object('code','billing_catalog_version_unavailable'); END IF;
          IF v_command.status='succeeded' THEN
            IF v_command.provider_command_reference=p_checkout_reference THEN
              RETURN jsonb_build_object('code','replayed');
            END IF;
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          v_expected_price:='sim_price_' || replace(p_plan_version_id::text,'-','');
          IF p_price_reference<>v_expected_price THEN
            RETURN jsonb_build_object('code','billing_catalog_version_unavailable');
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.plan_versions version JOIN public.plan_catalog plan ON plan.id=version.plan_id
            WHERE version.id=p_plan_version_id AND version.state='published' AND plan.state='published'
              AND version.currency=p_currency
          ) THEN RETURN jsonb_build_object('code','billing_catalog_version_unavailable'); END IF;

          SELECT * INTO v_customer FROM public.billing_customers
          WHERE organization_id=v_org AND provider=p_provider FOR UPDATE;
          IF FOUND AND v_customer.provider_customer_reference<>p_customer_reference THEN
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          IF NOT FOUND THEN
            INSERT INTO public.billing_customers(organization_id,provider,provider_customer_reference)
            VALUES(v_org,p_provider,p_customer_reference) RETURNING * INTO v_customer;
          END IF;
          SELECT * INTO v_subscription FROM public.subscriptions
          WHERE organization_id=v_org AND state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling')
          FOR UPDATE;
          IF FOUND THEN
            IF v_subscription.provider<>p_provider
               OR v_subscription.provider_subscription_reference<>p_subscription_reference
               OR v_subscription.billing_customer_id<>v_customer.id
               OR v_subscription.plan_version_id<>p_plan_version_id OR v_subscription.currency<>p_currency THEN
              RETURN jsonb_build_object('code','billing_subscription_exists');
            END IF;
          ELSE
            INSERT INTO public.subscriptions(
              organization_id,billing_customer_id,provider,provider_subscription_reference,plan_version_id,
              currency,state,current_period_start,current_period_end,cancel_at_period_end,provider_updated_at
            ) VALUES(
              v_org,v_customer.id,p_provider,p_subscription_reference,p_plan_version_id,
              p_currency,'pending_checkout',p_period_start,p_period_end,false,p_provider_updated_at
            );
          END IF;
          UPDATE public.billing_commands SET status='succeeded',provider_command_reference=p_checkout_reference,
            updated_at=clock_timestamp(),version=version+1 WHERE id=v_command.id;
          PERFORM app_private.append_audit_event(
            gen_random_uuid(),'tenant',v_org,'user',v_actor,'billing.checkout_session_created',
            'billing_command',v_command.id,v_request,v_request,'api',
            jsonb_build_object('command_kind','checkout','replayed',false),1::smallint
          );
          RETURN jsonb_build_object('code','succeeded');
        END $fn$;
        """
    )


def downgrade() -> None:
    op.execute(
        "LOCK TABLE public.billing_commands, public.subscriptions, public.plan_versions IN ACCESS EXCLUSIVE MODE"
    )
    op.execute(
        r"""
        DO $guard$
        BEGIN
          IF EXISTS (SELECT 1 FROM public.subscriptions WHERE currency <> 'CAD')
             OR EXISTS (
               SELECT 1 FROM public.billing_commands c
               WHERE c.command_kind = 'checkout'
                 AND NOT EXISTS (
                   SELECT 1 FROM public.plan_versions v
                   WHERE v.currency = 'CAD' AND c.request_fingerprint =
                     encode(sha256(convert_to('["checkout","' || v.id::text || '","subscription"]', 'UTF8')), 'hex')
                 )
             ) THEN
            RAISE EXCEPTION 'P53-06B rollback blocked: non-CAD or unidentifiable checkout data exists';
          END IF;
        END $guard$;
        """
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.prepare_billing_checkout(
          p_command_id uuid, p_plan_version_id uuid, p_key_digest text,
          p_request_fingerprint text, p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_org uuid:=app_private.current_organization_id();
          v_actor uuid:=app_private.current_actor_id();
          v_request text:=current_setting('app.request_id',true);
          v_existing public.billing_commands%ROWTYPE;
          v_version public.plan_versions%ROWTYPE;
          v_plan_state text;
          v_active_limit bigint;
          v_pending_limit bigint;
          v_active_count bigint;
          v_pending_count bigint;
          v_price_reference text;
        BEGIN
          IF v_org IS NULL OR v_actor IS NULL OR p_command_id IS NULL OR p_plan_version_id IS NULL OR p_now IS NULL
             OR p_key_digest !~ '^[a-f0-9]{64}$' OR p_request_fingerprint !~ '^[a-f0-9]{64}$' THEN
            RETURN jsonb_build_object('code','billing_catalog_version_unavailable');
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.memberships m JOIN public.organizations o ON o.id=m.organization_id
            WHERE m.organization_id=v_org AND m.user_id=v_actor AND m.status='active'
              AND m.role='admin' AND o.status='active'
          ) THEN RETURN jsonb_build_object('code','billing_capability_required'); END IF;

          SELECT * INTO v_existing FROM public.billing_commands
          WHERE organization_id=v_org AND idempotency_key_digest=p_key_digest FOR UPDATE;
          IF FOUND THEN
            IF v_existing.command_kind<>'checkout' OR v_existing.request_fingerprint<>p_request_fingerprint THEN
              RETURN jsonb_build_object('code','billing_command_conflict');
            END IF;
          END IF;

          SELECT * INTO v_version FROM public.plan_versions WHERE id=p_plan_version_id;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','billing_catalog_version_unavailable'); END IF;
          SELECT state INTO v_plan_state FROM public.plan_catalog WHERE id=v_version.plan_id;
          IF v_existing.id IS NULL AND (
             v_version.state<>'published' OR v_plan_state<>'published'
             OR v_version.effective_from>p_now
             OR (v_version.effective_until IS NOT NULL AND v_version.effective_until<=p_now)
          ) THEN
            RETURN jsonb_build_object('code','billing_catalog_version_unavailable');
          END IF;
          IF v_version.currency<>'CAD' THEN
            RETURN jsonb_build_object('code','billing_currency_unavailable');
          END IF;

          SELECT integer_value INTO v_active_limit FROM public.plan_entitlements
          WHERE plan_version_id=p_plan_version_id AND entitlement_key='seats.active_members.max' AND value_kind='limit';
          SELECT integer_value INTO v_pending_limit FROM public.plan_entitlements
          WHERE plan_version_id=p_plan_version_id AND entitlement_key='seats.pending_invitations.max' AND value_kind='limit';
          IF v_active_limit IS NULL OR v_pending_limit IS NULL THEN
            RETURN jsonb_build_object('code','billing_catalog_version_unavailable');
          END IF;
          SELECT count(*) INTO v_active_count FROM public.memberships
          WHERE organization_id=v_org AND status='active';
          SELECT count(*) INTO v_pending_count FROM public.user_invitations
          WHERE organization_id=v_org AND invitation_kind='member' AND accepted_at IS NULL
            AND revoked_at IS NULL AND expires_at>p_now;
          IF v_existing.id IS NULL
             AND (v_active_count+v_pending_count>v_active_limit OR v_pending_count>v_pending_limit) THEN
            RETURN jsonb_build_object('code','billing_seat_limit_conflict');
          END IF;

          v_price_reference:='sim_price_' || replace(p_plan_version_id::text,'-','');
          IF v_existing.id IS NOT NULL THEN
            RETURN jsonb_build_object(
              'code','replayed','command_id',v_existing.id,'status',v_existing.status,
              'plan_version_id',p_plan_version_id,'currency',v_version.currency,
              'provider_price_reference',v_price_reference
            );
          END IF;
          IF EXISTS (
            SELECT 1 FROM public.subscriptions WHERE organization_id=v_org
              AND state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling')
          ) THEN RETURN jsonb_build_object('code','billing_subscription_exists'); END IF;

          INSERT INTO public.billing_commands(
            id,organization_id,command_kind,idempotency_key_digest,request_fingerprint,status,created_at,updated_at
          ) VALUES (p_command_id,v_org,'checkout',p_key_digest,p_request_fingerprint,'reserved',p_now,p_now)
          ON CONFLICT (organization_id,idempotency_key_digest) DO NOTHING;
          IF NOT FOUND THEN
            SELECT * INTO v_existing FROM public.billing_commands
            WHERE organization_id=v_org AND idempotency_key_digest=p_key_digest FOR UPDATE;
            IF v_existing.command_kind<>'checkout' OR v_existing.request_fingerprint<>p_request_fingerprint THEN
              RETURN jsonb_build_object('code','billing_command_conflict');
            END IF;
            RETURN jsonb_build_object(
              'code','replayed','command_id',v_existing.id,'status',v_existing.status,
              'plan_version_id',p_plan_version_id,'currency',v_version.currency,
              'provider_price_reference',v_price_reference
            );
          END IF;
          PERFORM app_private.append_audit_event(
            gen_random_uuid(),'tenant',v_org,'user',v_actor,'billing.checkout_requested',
            'billing_command',p_command_id,v_request,v_request,'api',
            jsonb_build_object('command_kind','checkout','replayed',false),1::smallint
          );
          RETURN jsonb_build_object(
            'code','reserved','command_id',p_command_id,'status','reserved',
            'plan_version_id',p_plan_version_id,'currency',v_version.currency,
            'provider_price_reference',v_price_reference
          );
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.complete_billing_checkout(
          p_command_id uuid, p_plan_version_id uuid, p_provider text, p_checkout_reference text,
          p_customer_reference text, p_subscription_reference text, p_currency text, p_price_reference text,
          p_period_start timestamptz, p_period_end timestamptz, p_provider_updated_at timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_org uuid:=app_private.current_organization_id();
          v_actor uuid:=app_private.current_actor_id();
          v_request text:=current_setting('app.request_id',true);
          v_command public.billing_commands%ROWTYPE;
          v_customer public.billing_customers%ROWTYPE;
          v_subscription public.subscriptions%ROWTYPE;
          v_expected_price text;
        BEGIN
          SELECT * INTO v_command FROM public.billing_commands
          WHERE id=p_command_id AND organization_id=v_org AND command_kind='checkout' FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','billing_state_unknown'); END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.memberships m JOIN public.organizations o ON o.id=m.organization_id
            WHERE m.organization_id=v_org AND m.user_id=v_actor AND m.status='active'
              AND m.role='admin' AND o.status='active'
          ) THEN RETURN jsonb_build_object('code','billing_capability_required'); END IF;
          IF v_command.status='unknown' THEN RETURN jsonb_build_object('code','billing_reconciliation_required'); END IF;
          IF p_provider<>'simulated' OR p_checkout_reference IS NULL OR btrim(p_checkout_reference)=''
             OR p_customer_reference IS NULL OR btrim(p_customer_reference)=''
             OR p_subscription_reference IS NULL OR btrim(p_subscription_reference)=''
             OR p_currency<>'CAD' OR p_period_start IS NULL OR p_period_end<=p_period_start
             OR p_provider_updated_at IS NULL THEN
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          IF v_command.status='succeeded' THEN
            IF v_command.provider_command_reference=p_checkout_reference THEN
              RETURN jsonb_build_object('code','replayed');
            END IF;
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          v_expected_price:='sim_price_' || replace(p_plan_version_id::text,'-','');
          IF p_price_reference<>v_expected_price THEN
            RETURN jsonb_build_object('code','billing_catalog_version_unavailable');
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.plan_versions version JOIN public.plan_catalog plan ON plan.id=version.plan_id
            WHERE version.id=p_plan_version_id AND version.state='published' AND plan.state='published'
              AND version.currency=p_currency
          ) THEN RETURN jsonb_build_object('code','billing_catalog_version_unavailable'); END IF;

          SELECT * INTO v_customer FROM public.billing_customers
          WHERE organization_id=v_org AND provider=p_provider FOR UPDATE;
          IF FOUND AND v_customer.provider_customer_reference<>p_customer_reference THEN
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          IF NOT FOUND THEN
            INSERT INTO public.billing_customers(organization_id,provider,provider_customer_reference)
            VALUES(v_org,p_provider,p_customer_reference) RETURNING * INTO v_customer;
          END IF;
          SELECT * INTO v_subscription FROM public.subscriptions
          WHERE organization_id=v_org AND state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling')
          FOR UPDATE;
          IF FOUND THEN
            IF v_subscription.provider<>p_provider
               OR v_subscription.provider_subscription_reference<>p_subscription_reference
               OR v_subscription.billing_customer_id<>v_customer.id
               OR v_subscription.plan_version_id<>p_plan_version_id OR v_subscription.currency<>p_currency THEN
              RETURN jsonb_build_object('code','billing_subscription_exists');
            END IF;
          ELSE
            INSERT INTO public.subscriptions(
              organization_id,billing_customer_id,provider,provider_subscription_reference,plan_version_id,
              currency,state,current_period_start,current_period_end,cancel_at_period_end,provider_updated_at
            ) VALUES(
              v_org,v_customer.id,p_provider,p_subscription_reference,p_plan_version_id,
              p_currency,'pending_checkout',p_period_start,p_period_end,false,p_provider_updated_at
            );
          END IF;
          UPDATE public.billing_commands SET status='succeeded',provider_command_reference=p_checkout_reference,
            updated_at=clock_timestamp(),version=version+1 WHERE id=v_command.id;
          PERFORM app_private.append_audit_event(
            gen_random_uuid(),'tenant',v_org,'user',v_actor,'billing.checkout_session_created',
            'billing_command',v_command.id,v_request,v_request,'api',
            jsonb_build_object('command_kind','checkout','replayed',false),1::smallint
          );
          RETURN jsonb_build_object('code','succeeded');
        END $fn$;
        """
    )
