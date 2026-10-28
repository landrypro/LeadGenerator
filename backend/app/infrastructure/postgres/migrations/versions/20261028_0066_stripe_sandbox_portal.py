"""Restrict Stripe sandbox portal sessions to the tenant's Stripe customer."""

from alembic import op

revision = "20261028_0066"
down_revision = "20261027_0065"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "app_private.prepare_stripe_sandbox_portal(uuid,text,text,timestamptz)",
    "app_private.complete_stripe_sandbox_portal(uuid,text)",
)


def upgrade() -> None:
    op.execute(r"""
        CREATE FUNCTION app_private.prepare_stripe_sandbox_portal(
          p_command_id uuid,p_key_digest text,p_request_fingerprint text,p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_org uuid:=app_private.current_organization_id(); v_actor uuid:=app_private.current_actor_id();
          v_request text:=current_setting('app.request_id',true); v_existing public.billing_commands%ROWTYPE;
          v_customer text;
        BEGIN
          IF v_org IS NULL OR v_actor IS NULL OR p_command_id IS NULL OR p_now IS NULL
             OR p_key_digest !~ '^[a-f0-9]{64}$' OR p_request_fingerprint !~ '^[a-f0-9]{64}$' THEN
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          IF NOT EXISTS(
            SELECT 1 FROM public.memberships m JOIN public.organizations o ON o.id=m.organization_id
            WHERE m.organization_id=v_org AND m.user_id=v_actor AND m.status='active' AND m.role='admin'
              AND o.status='active'
          ) THEN RETURN jsonb_build_object('code','billing_capability_required'); END IF;
          SELECT * INTO v_existing FROM public.billing_commands
          WHERE organization_id=v_org AND idempotency_key_digest=p_key_digest FOR UPDATE;
          IF FOUND AND (v_existing.command_kind<>'portal' OR v_existing.request_fingerprint<>p_request_fingerprint) THEN
            RETURN jsonb_build_object('code','billing_command_conflict');
          END IF;
          SELECT c.provider_customer_reference INTO v_customer FROM public.billing_customers c
          WHERE c.organization_id=v_org AND c.provider='stripe';
          IF v_customer IS NULL OR NOT EXISTS(
            SELECT 1 FROM public.subscriptions s JOIN public.billing_customers c ON c.id=s.billing_customer_id
            WHERE s.organization_id=v_org AND s.provider='stripe' AND c.provider_customer_reference=v_customer
              AND s.state IN ('active','past_due','grace_period','suspended','canceling')
          ) THEN RETURN jsonb_build_object('code','billing_state_unknown'); END IF;
          -- A matching command is a replay only after the customer and the
          -- subscription have been proved to belong to this tenant.  Do not
          -- rely on PL/pgSQL's mutable FOUND flag after the policy checks.
          IF v_existing.id IS NOT NULL THEN
            RETURN jsonb_build_object('code','replayed','command_id',v_existing.id,'status',v_existing.status,
              'provider_customer_reference',v_customer);
          END IF;
          INSERT INTO public.billing_commands(
            id,organization_id,command_kind,idempotency_key_digest,request_fingerprint,status,created_at,updated_at
          ) VALUES(p_command_id,v_org,'portal',p_key_digest,p_request_fingerprint,'reserved',p_now,p_now)
          ON CONFLICT (organization_id,idempotency_key_digest) DO NOTHING;
          IF NOT FOUND THEN
            SELECT * INTO v_existing FROM public.billing_commands
            WHERE organization_id=v_org AND idempotency_key_digest=p_key_digest FOR UPDATE;
            IF v_existing.command_kind<>'portal' OR v_existing.request_fingerprint<>p_request_fingerprint THEN
              RETURN jsonb_build_object('code','billing_command_conflict');
            END IF;
            RETURN jsonb_build_object('code','replayed','command_id',v_existing.id,'status',v_existing.status,
              'provider_customer_reference',v_customer);
          END IF;
          PERFORM app_private.append_audit_event(
            gen_random_uuid(),'tenant',v_org,'user',v_actor,'billing.portal_requested',
            'billing_command',p_command_id,v_request,v_request,'api',
            jsonb_build_object('command_kind','portal','replayed',false),1::smallint
          );
          RETURN jsonb_build_object('code','reserved','command_id',p_command_id,'status','reserved',
            'provider_customer_reference',v_customer);
        END $fn$
    """)
    op.execute(r"""
        CREATE FUNCTION app_private.complete_stripe_sandbox_portal(p_command_id uuid,p_portal_reference text)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_org uuid:=app_private.current_organization_id();
        BEGIN
          IF v_org IS NULL OR p_portal_reference !~ '^bps_[A-Za-z0-9_]+$'
             OR NOT EXISTS(SELECT 1 FROM public.billing_customers WHERE organization_id=v_org AND provider='stripe') THEN
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          RETURN app_private.complete_billing_portal(p_command_id,p_portal_reference);
        END $fn$
    """)
    for signature in _FUNCTIONS:
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")


def downgrade() -> None:
    for signature in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {signature}")
