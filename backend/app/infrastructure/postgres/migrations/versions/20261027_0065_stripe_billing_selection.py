"""Safe initial plan selection and tenant-visible Stripe sandbox billing state."""

from alembic import op

revision = "20261027_0065"
down_revision = "20261027_0064"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "app_private.prepare_stripe_sandbox_checkout_v2(uuid,uuid,text,text,timestamptz)",
    "app_private.tenant_stripe_billing_state()",
    "app_private.tenant_stripe_checkout_reference(uuid)",
)


def upgrade() -> None:
    op.execute(r"""
        CREATE FUNCTION app_private.prepare_stripe_sandbox_checkout_v2(
          p_command_id uuid,p_plan_version_id uuid,p_key_digest text,p_request_fingerprint text,p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_org uuid:=app_private.current_organization_id(); v_actor uuid:=app_private.current_actor_id();
          v_existing public.billing_commands%ROWTYPE; v_contract public.organization_plan_contracts%ROWTYPE;
          v_result jsonb;
        BEGIN
          IF v_org IS NULL OR v_actor IS NULL OR p_now IS NULL OR p_key_digest !~ '^[a-f0-9]{64}$'
             OR NOT EXISTS(SELECT 1 FROM public.memberships m JOIN public.organizations o ON o.id=m.organization_id
               WHERE m.organization_id=v_org AND m.user_id=v_actor AND m.status='active' AND m.role='admin'
                 AND o.status='active') THEN
            RETURN jsonb_build_object('code','billing_capability_required');
          END IF;
          PERFORM pg_advisory_xact_lock(hashtextextended('stripe-checkout:'||v_org::text,0));
          SELECT * INTO v_existing FROM public.billing_commands
          WHERE organization_id=v_org AND idempotency_key_digest=p_key_digest FOR UPDATE;
          IF NOT FOUND THEN
            IF EXISTS(SELECT 1 FROM public.subscriptions WHERE organization_id=v_org
              AND state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling'))
              OR EXISTS(SELECT 1 FROM public.organization_plan_contracts WHERE organization_id=v_org
                AND state IN ('active','suspended'))
              OR EXISTS(SELECT 1 FROM public.organization_plan_contracts WHERE organization_id=v_org
                AND state='pending' AND plan_version_id<>p_plan_version_id)
              OR EXISTS(SELECT 1 FROM public.stripe_sandbox_checkout_sessions WHERE organization_id=v_org
                AND completed_at IS NULL AND provider_subscription_reference IS NULL) THEN
              RETURN jsonb_build_object('code','billing_subscription_exists');
            END IF;
            IF EXISTS(SELECT 1 FROM public.billing_commands WHERE organization_id=v_org
              AND command_kind='checkout' AND status IN ('reserved','unknown')) THEN
              RETURN jsonb_build_object('code','billing_reconciliation_required');
            END IF;
          ELSIF v_existing.command_kind='checkout' AND v_existing.status='reserved'
            AND v_existing.created_at<clock_timestamp()-interval '1 hour' THEN
            RETURN jsonb_build_object('code','billing_reconciliation_required');
          END IF;
          v_result:=app_private.prepare_stripe_sandbox_checkout(
            p_command_id,p_plan_version_id,p_key_digest,p_request_fingerprint,p_now);
          IF v_result->>'code' NOT IN ('reserved','replayed') THEN RETURN v_result; END IF;
          SELECT * INTO v_contract FROM public.organization_plan_contracts
            WHERE organization_id=v_org AND state IN ('pending','active','suspended') FOR UPDATE;
          IF FOUND THEN
            IF v_contract.state<>'pending' OR v_contract.plan_version_id<>p_plan_version_id THEN
              RAISE EXCEPTION 'concurrent billing contract change';
            END IF;
          ELSE
            INSERT INTO public.organization_plan_contracts(
              organization_id,plan_version_id,state,currency,effective_from,
              created_by_user_id,updated_by_user_id)
            VALUES(v_org,p_plan_version_id,'pending',v_result->>'currency',p_now,v_actor,v_actor);
          END IF;
          RETURN v_result;
        END $fn$
    """)
    op.execute(r"""
        CREATE FUNCTION app_private.tenant_stripe_billing_state() RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_org uuid:=app_private.current_organization_id(); v_actor uuid:=app_private.current_actor_id();
          v_contract jsonb; v_subscription jsonb; v_checkout jsonb; v_command jsonb;
        BEGIN
          IF v_org IS NULL OR v_actor IS NULL OR NOT EXISTS(
            SELECT 1 FROM public.memberships m JOIN public.organizations o ON o.id=m.organization_id
            WHERE m.organization_id=v_org AND m.user_id=v_actor AND m.status='active' AND m.role='admin'
              AND o.status='active') THEN RETURN NULL; END IF;
          SELECT jsonb_build_object('state',c.state,'currency',c.currency,'plan_version_id',c.plan_version_id,
            'plan_code',p.code,'version_number',v.version_number,'effective_until',c.effective_until)
          INTO v_contract FROM public.organization_plan_contracts c
          JOIN public.plan_versions v ON v.id=c.plan_version_id JOIN public.plan_catalog p ON p.id=v.plan_id
          WHERE c.organization_id=v_org AND c.state IN ('pending','active','suspended') LIMIT 1;
          SELECT jsonb_build_object('state',s.state,'provider',s.provider,'plan_version_id',s.plan_version_id,
            'plan_code',p.code,'version_number',v.version_number,'currency',s.currency,
            'current_period_end',s.current_period_end,
            'cancel_at_period_end',s.cancel_at_period_end,'grace_ends_at',s.grace_ends_at,
            'paid_until',s.stripe_paid_until) INTO v_subscription FROM public.subscriptions s
          JOIN public.plan_versions v ON v.id=s.plan_version_id JOIN public.plan_catalog p ON p.id=v.plan_id
          WHERE s.organization_id=v_org ORDER BY CASE WHEN s.state='canceled' THEN 1 ELSE 0 END,s.created_at DESC LIMIT 1;
          SELECT jsonb_build_object('reference',c.provider_checkout_reference,'command_id',c.billing_command_id,
            'customer_reference',bc.provider_customer_reference,'price_reference',c.provider_price_reference,
            'plan_version_id',c.plan_version_id,'currency',c.currency,'expires_at',c.expires_at,
            'state',CASE WHEN c.expires_at<=clock_timestamp() THEN 'expired' ELSE 'open' END)
          INTO v_checkout FROM public.stripe_sandbox_checkout_sessions c
          JOIN public.billing_customers bc ON bc.id=c.billing_customer_id AND bc.organization_id=c.organization_id
          WHERE c.organization_id=v_org AND c.completed_at IS NULL AND c.provider_subscription_reference IS NULL
          ORDER BY c.created_at DESC LIMIT 1;
          SELECT jsonb_build_object('state',status,'created_at',created_at) INTO v_command
          FROM public.billing_commands WHERE organization_id=v_org AND command_kind='checkout'
            AND status IN ('reserved','unknown') ORDER BY created_at DESC LIMIT 1;
          RETURN jsonb_build_object('contract',v_contract,'subscription',v_subscription,
            'checkout',v_checkout,'command',v_command);
        END $fn$
    """)
    op.execute(r"""
        CREATE FUNCTION app_private.tenant_stripe_checkout_reference(p_command_id uuid) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_org uuid:=app_private.current_organization_id(); v_actor uuid:=app_private.current_actor_id();
          v_reference text;
        BEGIN
          IF v_org IS NULL OR v_actor IS NULL OR p_command_id IS NULL OR NOT EXISTS(
            SELECT 1 FROM public.memberships m JOIN public.organizations o ON o.id=m.organization_id
            WHERE m.organization_id=v_org AND m.user_id=v_actor AND m.status='active' AND m.role='admin'
              AND o.status='active') THEN RETURN NULL; END IF;
          SELECT provider_checkout_reference INTO v_reference
          FROM public.stripe_sandbox_checkout_sessions
          WHERE organization_id=v_org AND billing_command_id=p_command_id;
          RETURN v_reference;
        END $fn$
    """)
    for signature in _FUNCTIONS:
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")


def downgrade() -> None:
    for signature in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {signature}")
