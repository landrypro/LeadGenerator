"""Attributions sandbox distinctes de tout paiement Stripe (P53-10 DEV-05)."""

from alembic import op

revision = "20261030_0068"
down_revision = "20261029_0067"
branch_labels = None
depends_on = None

_ENTITLEMENT = "app_private.tenant_effective_entitlement(text,timestamp with time zone)"
_ENTITLEMENT_CONTRACT = "app_private.tenant_contract_effective_entitlement(text,timestamp with time zone)"
_BILLING_STATE = "app_private.tenant_stripe_billing_state()"
_BILLING_STATE_BASE = "app_private.tenant_stripe_billing_state_without_manual()"
_CHECKOUT = "app_private.prepare_stripe_sandbox_checkout_v2(uuid,uuid,text,text,timestamp with time zone)"
_CHECKOUT_BASE = (
    "app_private.prepare_stripe_sandbox_checkout_without_manual(uuid,uuid,text,text,timestamp with time zone)"
)
_MANUAL_FUNCTIONS = (
    "app_private.manual_billing_grant_payload(uuid,timestamp with time zone)",
    "app_private.list_platform_manual_billing_grant_options(timestamp with time zone)",
    "app_private.propose_platform_manual_billing_grant(uuid,uuid,text,text,uuid,uuid,text,integer,timestamp with time zone)",
    "app_private.approve_platform_manual_billing_grant(uuid,uuid,text,text,integer,timestamp with time zone)",
    "app_private.revoke_platform_manual_billing_grant(uuid,uuid,text,text,integer,timestamp with time zone)",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.manual_billing_grants (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          plan_version_id uuid NOT NULL REFERENCES public.plan_versions(id) ON DELETE RESTRICT,
          reason_code varchar(48) NOT NULL,
          duration_days smallint NOT NULL,
          state varchar(32) NOT NULL DEFAULT 'pending_approval',
          requested_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
          approved_by_user_id uuid NULL REFERENCES public.users(id) ON DELETE RESTRICT,
          revoked_by_user_id uuid NULL REFERENCES public.users(id) ON DELETE RESTRICT,
          starts_at timestamptz NULL,
          ends_at timestamptz NULL,
          approved_at timestamptz NULL,
          revoked_at timestamptz NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          version integer NOT NULL DEFAULT 1,
          CONSTRAINT ck_manual_billing_grants_reason_code CHECK (
            reason_code IN ('sandbox_validation','sandbox_support','sandbox_demonstration')
          ),
          CONSTRAINT ck_manual_billing_grants_duration_days CHECK (duration_days BETWEEN 1 AND 31),
          CONSTRAINT ck_manual_billing_grants_state CHECK (state IN ('pending_approval','active','revoked')),
          CONSTRAINT ck_manual_billing_grants_approver CHECK (
            approved_by_user_id IS NULL OR approved_by_user_id<>requested_by_user_id
          ),
          CONSTRAINT ck_manual_billing_grants_active_range CHECK (
            ends_at IS NULL OR (starts_at IS NOT NULL AND ends_at>starts_at)
          ),
          CONSTRAINT ck_manual_billing_grants_pending_shape CHECK (
            state<>'pending_approval' OR (approved_by_user_id IS NULL AND approved_at IS NULL
              AND starts_at IS NULL AND ends_at IS NULL)
          ),
          CONSTRAINT ck_manual_billing_grants_active_shape CHECK (
            state<>'active' OR (approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL
              AND starts_at IS NOT NULL AND ends_at IS NOT NULL
              AND revoked_by_user_id IS NULL AND revoked_at IS NULL)
          ),
          CONSTRAINT ck_manual_billing_grants_revoked_shape CHECK (
            state<>'revoked' OR (revoked_by_user_id IS NOT NULL AND revoked_at IS NOT NULL)
          ),
          CONSTRAINT ck_manual_billing_grants_version CHECK (version>0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_manual_billing_grants_org_state
          ON public.manual_billing_grants(organization_id,state,ends_at)
        """
    )
    op.execute(
        """
        CREATE TABLE public.manual_billing_grant_operations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          grant_id uuid NOT NULL REFERENCES public.manual_billing_grants(id) ON DELETE RESTRICT,
          actor_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
          command varchar(16) NOT NULL,
          idempotency_key_digest char(64) NOT NULL,
          request_fingerprint char(64) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT uq_manual_billing_grant_operations_actor_key UNIQUE(actor_id,idempotency_key_digest),
          CONSTRAINT ck_manual_billing_grant_operations_command CHECK (command IN ('propose','approve','revoke')),
          CONSTRAINT ck_manual_billing_grant_operations_key CHECK (idempotency_key_digest ~ '^[a-f0-9]{64}$'),
          CONSTRAINT ck_manual_billing_grant_operations_fingerprint CHECK (request_fingerprint ~ '^[a-f0-9]{64}$')
        )
        """
    )
    for table in ("manual_billing_grants", "manual_billing_grant_operations"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC, prospect_app, prospect_worker")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON public.{table} TO prospect_rls_definer")

    op.execute(
        r"""
        CREATE FUNCTION app_private.manual_billing_grant_payload(p_grant_id uuid,p_now timestamptz)
        RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
          SELECT jsonb_build_object(
            'id',g.id,'organization_id',g.organization_id,'plan_version_id',g.plan_version_id,
            'plan_code',p.code,'version_number',v.version_number,'currency',v.currency,
            'reason_code',g.reason_code,'duration_days',g.duration_days,
            'state',CASE WHEN g.state='active' AND g.ends_at<=p_now THEN 'expired' ELSE g.state END,
            'starts_at',g.starts_at,'ends_at',g.ends_at,'version',g.version
          )
          FROM public.manual_billing_grants g
          JOIN public.plan_versions v ON v.id=g.plan_version_id
          JOIN public.plan_catalog p ON p.id=v.plan_id
          WHERE g.id=p_grant_id
        $fn$
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.list_platform_manual_billing_grant_options(p_now timestamptz)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_payload jsonb;
        BEGIN
          IF v_actor IS NULL OR NOT EXISTS(
            SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin'
          ) THEN RAISE EXCEPTION 'platform_billing_forbidden' USING ERRCODE='42501'; END IF;
          SELECT jsonb_build_object('items',coalesce(jsonb_agg(jsonb_build_object(
            'plan_version_id',v.id,'code',p.code,'version_number',v.version_number,
            'currency',v.currency,'amount_minor',v.amount_excluding_tax_minor
          ) ORDER BY p.display_order,v.version_number,v.currency),'[]'::jsonb)) INTO v_payload
          FROM public.plan_versions v JOIN public.plan_catalog p ON p.id=v.plan_id
          WHERE p.state='published' AND v.state='published' AND v.billing_cycle='monthly'
            AND v.effective_from<=p_now AND (v.effective_until IS NULL OR v.effective_until>p_now);
          RETURN v_payload;
        END $fn$
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.propose_platform_manual_billing_grant(
          p_grant_id uuid,p_operation_id uuid,p_key_digest text,p_request_fingerprint text,
          p_organization_id uuid,p_plan_version_id uuid,p_reason_code text,p_duration_days integer,p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_existing public.manual_billing_grant_operations%ROWTYPE;
          v_grant public.manual_billing_grants%ROWTYPE; v_version public.plan_versions%ROWTYPE;
          v_plan_state text; v_payload jsonb;
        BEGIN
          IF v_actor IS NULL OR p_grant_id IS NULL OR p_operation_id IS NULL OR p_organization_id IS NULL
             OR p_plan_version_id IS NULL OR p_now IS NULL OR p_key_digest !~ '^[a-f0-9]{64}$'
             OR p_request_fingerprint !~ '^[a-f0-9]{64}$' OR p_reason_code NOT IN
                ('sandbox_validation','sandbox_support','sandbox_demonstration') OR p_duration_days NOT BETWEEN 1 AND 31 THEN
            RETURN jsonb_build_object('code','catalog_version_unavailable');
          END IF;
          IF NOT EXISTS(SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin') THEN
            RETURN jsonb_build_object('code','conflict');
          END IF;
          SELECT * INTO v_existing FROM public.manual_billing_grant_operations
          WHERE actor_id=v_actor AND idempotency_key_digest=p_key_digest FOR UPDATE;
          IF FOUND THEN
            IF v_existing.command<>'propose' OR v_existing.request_fingerprint<>p_request_fingerprint THEN
              RETURN jsonb_build_object('code','command_conflict');
            END IF;
            SELECT app_private.manual_billing_grant_payload(v_existing.grant_id,p_now) INTO v_payload;
            RETURN jsonb_build_object('code','replayed','grant',v_payload);
          END IF;
          PERFORM pg_advisory_xact_lock(hashtextextended('manual-billing-grant:'||p_organization_id::text,0));
          IF NOT EXISTS(SELECT 1 FROM public.organizations WHERE id=p_organization_id AND status='active') THEN
            RETURN jsonb_build_object('code','conflict');
          END IF;
          SELECT * INTO v_version FROM public.plan_versions WHERE id=p_plan_version_id;
          IF NOT FOUND THEN
            RETURN jsonb_build_object('code','catalog_version_unavailable');
          END IF;
          SELECT state INTO v_plan_state FROM public.plan_catalog WHERE id=v_version.plan_id;
          IF v_plan_state<>'published' OR v_version.state<>'published'
             OR v_version.billing_cycle<>'monthly' OR v_version.effective_from>p_now
             OR (v_version.effective_until IS NOT NULL AND v_version.effective_until<=p_now) THEN
            RETURN jsonb_build_object('code','catalog_version_unavailable');
          END IF;
          IF EXISTS(SELECT 1 FROM public.subscriptions WHERE organization_id=p_organization_id
              AND state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling'))
             OR EXISTS(SELECT 1 FROM public.organization_plan_contracts WHERE organization_id=p_organization_id
              AND state IN ('pending','active','suspended'))
             OR EXISTS(SELECT 1 FROM public.manual_billing_grants WHERE organization_id=p_organization_id
              AND (state='pending_approval' OR (state='active' AND ends_at>p_now))) THEN
            RETURN jsonb_build_object('code','conflict');
          END IF;
          INSERT INTO public.manual_billing_grants(
            id,organization_id,plan_version_id,reason_code,duration_days,state,requested_by_user_id,created_at,updated_at
          ) VALUES(
            p_grant_id,p_organization_id,p_plan_version_id,p_reason_code,p_duration_days,'pending_approval',v_actor,p_now,p_now
          ) RETURNING * INTO v_grant;
          INSERT INTO public.manual_billing_grant_operations(
            id,grant_id,actor_id,command,idempotency_key_digest,request_fingerprint,created_at
          ) VALUES(p_operation_id,v_grant.id,v_actor,'propose',p_key_digest,p_request_fingerprint,p_now);
          SELECT app_private.manual_billing_grant_payload(v_grant.id,p_now) INTO v_payload;
          RETURN jsonb_build_object('code','created','grant',v_payload);
        END $fn$
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.approve_platform_manual_billing_grant(
          p_grant_id uuid,p_operation_id uuid,p_key_digest text,p_request_fingerprint text,p_expected_version integer,p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_existing public.manual_billing_grant_operations%ROWTYPE;
          v_grant public.manual_billing_grants%ROWTYPE; v_payload jsonb;
        BEGIN
          IF v_actor IS NULL OR p_grant_id IS NULL OR p_operation_id IS NULL OR p_expected_version<1 OR p_now IS NULL
             OR p_key_digest !~ '^[a-f0-9]{64}$' OR p_request_fingerprint !~ '^[a-f0-9]{64}$' THEN
            RETURN jsonb_build_object('code','invalid_state');
          END IF;
          IF NOT EXISTS(SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin') THEN
            RETURN jsonb_build_object('code','conflict');
          END IF;
          SELECT * INTO v_existing FROM public.manual_billing_grant_operations
          WHERE actor_id=v_actor AND idempotency_key_digest=p_key_digest FOR UPDATE;
          IF FOUND THEN
            IF v_existing.command<>'approve' OR v_existing.request_fingerprint<>p_request_fingerprint
               OR v_existing.grant_id<>p_grant_id THEN RETURN jsonb_build_object('code','command_conflict'); END IF;
            SELECT app_private.manual_billing_grant_payload(v_existing.grant_id,p_now) INTO v_payload;
            RETURN jsonb_build_object('code','replayed','grant',v_payload);
          END IF;
          SELECT * INTO v_grant FROM public.manual_billing_grants WHERE id=p_grant_id FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','not_found'); END IF;
          IF v_grant.version<>p_expected_version THEN
            RETURN jsonb_build_object('code','version_conflict','current_version',v_grant.version);
          END IF;
          IF v_grant.requested_by_user_id=v_actor THEN RETURN jsonb_build_object('code','approval_required'); END IF;
          IF v_grant.state<>'pending_approval' THEN RETURN jsonb_build_object('code','invalid_state'); END IF;
          PERFORM pg_advisory_xact_lock(hashtextextended('manual-billing-grant:'||v_grant.organization_id::text,0));
          IF EXISTS(SELECT 1 FROM public.subscriptions WHERE organization_id=v_grant.organization_id
              AND state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling'))
             OR EXISTS(SELECT 1 FROM public.organization_plan_contracts WHERE organization_id=v_grant.organization_id
              AND state IN ('pending','active','suspended'))
             OR EXISTS(SELECT 1 FROM public.manual_billing_grants WHERE organization_id=v_grant.organization_id
              AND id<>v_grant.id AND state='active' AND ends_at>p_now) THEN
            RETURN jsonb_build_object('code','conflict');
          END IF;
          UPDATE public.manual_billing_grants SET state='active',approved_by_user_id=v_actor,approved_at=p_now,
            starts_at=p_now,ends_at=p_now+make_interval(days=>duration_days),updated_at=p_now,version=version+1
          WHERE id=v_grant.id RETURNING * INTO v_grant;
          INSERT INTO public.manual_billing_grant_operations(
            id,grant_id,actor_id,command,idempotency_key_digest,request_fingerprint,created_at
          ) VALUES(p_operation_id,v_grant.id,v_actor,'approve',p_key_digest,p_request_fingerprint,p_now);
          SELECT app_private.manual_billing_grant_payload(v_grant.id,p_now) INTO v_payload;
          RETURN jsonb_build_object('code','approved','grant',v_payload);
        END $fn$
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.revoke_platform_manual_billing_grant(
          p_grant_id uuid,p_operation_id uuid,p_key_digest text,p_request_fingerprint text,p_expected_version integer,p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_existing public.manual_billing_grant_operations%ROWTYPE;
          v_grant public.manual_billing_grants%ROWTYPE; v_payload jsonb;
        BEGIN
          IF v_actor IS NULL OR p_grant_id IS NULL OR p_operation_id IS NULL OR p_expected_version<1 OR p_now IS NULL
             OR p_key_digest !~ '^[a-f0-9]{64}$' OR p_request_fingerprint !~ '^[a-f0-9]{64}$' THEN
            RETURN jsonb_build_object('code','invalid_state');
          END IF;
          IF NOT EXISTS(SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin') THEN
            RETURN jsonb_build_object('code','conflict');
          END IF;
          SELECT * INTO v_existing FROM public.manual_billing_grant_operations
          WHERE actor_id=v_actor AND idempotency_key_digest=p_key_digest FOR UPDATE;
          IF FOUND THEN
            IF v_existing.command<>'revoke' OR v_existing.request_fingerprint<>p_request_fingerprint
               OR v_existing.grant_id<>p_grant_id THEN RETURN jsonb_build_object('code','command_conflict'); END IF;
            SELECT app_private.manual_billing_grant_payload(v_existing.grant_id,p_now) INTO v_payload;
            RETURN jsonb_build_object('code','replayed','grant',v_payload);
          END IF;
          SELECT * INTO v_grant FROM public.manual_billing_grants WHERE id=p_grant_id FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','not_found'); END IF;
          IF v_grant.version<>p_expected_version THEN
            RETURN jsonb_build_object('code','version_conflict','current_version',v_grant.version);
          END IF;
          IF v_grant.state NOT IN ('pending_approval','active')
             OR (v_grant.state='active' AND v_grant.ends_at<=p_now) THEN
            RETURN jsonb_build_object('code','invalid_state');
          END IF;
          UPDATE public.manual_billing_grants SET state='revoked',revoked_by_user_id=v_actor,revoked_at=p_now,
            updated_at=p_now,version=version+1 WHERE id=v_grant.id RETURNING * INTO v_grant;
          INSERT INTO public.manual_billing_grant_operations(
            id,grant_id,actor_id,command,idempotency_key_digest,request_fingerprint,created_at
          ) VALUES(p_operation_id,v_grant.id,v_actor,'revoke',p_key_digest,p_request_fingerprint,p_now);
          SELECT app_private.manual_billing_grant_payload(v_grant.id,p_now) INTO v_payload;
          RETURN jsonb_build_object('code','revoked','grant',v_payload);
        END $fn$
        """
    )

    # Preserve the previous entitlement routine verbatim as the paid/catalog
    # branch, then place the manual-grant branch in front of it. This prevents
    # a manual right from ever being represented as a paid local contract.
    op.execute(
        r"""
        DO $copy$
        DECLARE v_definition text;
        BEGIN
          SELECT pg_get_functiondef('app_private.tenant_effective_entitlement(text,timestamp with time zone)'::regprocedure)
            INTO v_definition;
          v_definition:=replace(v_definition,'FUNCTION app_private.tenant_effective_entitlement(',
            'FUNCTION app_private.tenant_contract_effective_entitlement(');
          EXECUTE v_definition;
        END $copy$
        """
    )
    op.execute(f"ALTER FUNCTION {_ENTITLEMENT_CONTRACT} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_ENTITLEMENT_CONTRACT} FROM PUBLIC, prospect_app, prospect_worker")
    op.execute("GRANT SELECT ON public.manual_billing_grants TO prospect_rls_definer")
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.tenant_effective_entitlement(p_entitlement_key text,p_now timestamptz)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_org uuid:=app_private.current_organization_id(); v_grant_count integer; v_contract_count integer;
          v_subscription_count integer;
          v_grant public.manual_billing_grants%ROWTYPE; v_version public.plan_versions%ROWTYPE;
          v_entitlement public.plan_entitlements%ROWTYPE; v_safety public.entitlement_safety_ceilings%ROWTYPE;
          v_provenance jsonb; v_value_kind text; v_integer_value bigint; v_boolean_value boolean;
        BEGIN
          IF p_entitlement_key NOT IN (
            'seats.active_members.max','seats.pending_invitations.max','prospects.active.max',
            'exports.monthly.max','imports.rows_per_run.max','google.paid_calls.enabled',
            'automation.prepare.enabled','automation.execute.enabled'
          ) THEN RETURN jsonb_build_object('code','entitlement_unknown','key',p_entitlement_key,
            'reason','entitlement_unknown','provenance','[]'::jsonb); END IF;
          SELECT count(*) INTO v_grant_count FROM public.manual_billing_grants
          WHERE organization_id=v_org AND state='active' AND starts_at<=p_now AND ends_at>p_now;
          IF v_grant_count=0 THEN
            RETURN app_private.tenant_contract_effective_entitlement(p_entitlement_key,p_now);
          END IF;
          SELECT count(*) INTO v_contract_count FROM public.organization_plan_contracts
          WHERE organization_id=v_org AND state='active' AND effective_from<=p_now
            AND (effective_until IS NULL OR effective_until>p_now);
          SELECT count(*) INTO v_subscription_count FROM public.subscriptions
          WHERE organization_id=v_org AND state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling');
          IF v_grant_count<>1 OR v_contract_count<>0 OR v_subscription_count<>0 THEN
            RETURN jsonb_build_object('code','deny_unknown_contract','key',p_entitlement_key,
              'reason','ambiguous_active_entitlement_source',
              'provenance',jsonb_build_array(
                jsonb_build_object('source','manual_grant','applied',false),
                jsonb_build_object('source','contract','applied',false)
              ));
          END IF;
          SELECT * INTO v_grant FROM public.manual_billing_grants WHERE organization_id=v_org AND state='active'
            AND starts_at<=p_now AND ends_at>p_now;
          IF v_grant.approved_by_user_id IS NULL OR v_grant.approved_by_user_id=v_grant.requested_by_user_id THEN
            RETURN jsonb_build_object('code','deny_unknown_contract','key',p_entitlement_key,
              'reason','manual_grant_not_approved',
              'provenance',jsonb_build_array(jsonb_build_object('source','manual_grant','applied',false)));
          END IF;
          v_provenance:=jsonb_build_array(jsonb_build_object('source','manual_grant','applied',true));
          SELECT * INTO v_version FROM public.plan_versions WHERE id=v_grant.plan_version_id;
          IF NOT FOUND OR v_version.state<>'published' OR v_version.effective_from>p_now
             OR (v_version.effective_until IS NOT NULL AND v_version.effective_until<=p_now) THEN
            RETURN jsonb_build_object('code','deny_unknown_contract','key',p_entitlement_key,
              'reason','catalog_version_not_effective','provenance',v_provenance);
          END IF;
          v_provenance:=v_provenance||jsonb_build_array(jsonb_build_object('source','plan_version','applied',true));
          SELECT * INTO v_entitlement FROM public.plan_entitlements
          WHERE plan_version_id=v_version.id AND entitlement_key=p_entitlement_key;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','entitlement_unknown','key',p_entitlement_key,
            'reason','plan_entitlement_missing','provenance',v_provenance); END IF;
          v_value_kind:=v_entitlement.value_kind; v_integer_value:=v_entitlement.integer_value;
          v_boolean_value:=v_entitlement.boolean_value;
          SELECT * INTO v_safety FROM public.entitlement_safety_ceilings WHERE entitlement_key=p_entitlement_key;
          IF FOUND THEN
            IF v_safety.value_kind<>v_value_kind
              OR (v_value_kind='limit' AND v_integer_value>v_safety.integer_value)
              OR (v_value_kind='switch' AND v_boolean_value AND NOT v_safety.boolean_value) THEN
              RETURN jsonb_build_object('code','safety_ceiling_exceeded','key',p_entitlement_key,
                'source','manual_grant','reason','safety_ceiling_exceeded',
                'provenance',v_provenance||jsonb_build_array(jsonb_build_object('source','safety_ceiling','applied',false)));
            END IF;
            v_provenance:=v_provenance||jsonb_build_array(jsonb_build_object('source','safety_ceiling','applied',true));
          END IF;
          RETURN jsonb_build_object('code',CASE WHEN (v_value_kind='limit' AND v_integer_value=0)
              OR (v_value_kind='switch' AND NOT v_boolean_value) THEN 'entitlement_disabled' ELSE 'allowed' END,
            'key',p_entitlement_key,'source','manual_grant','value_kind',v_value_kind,
            'integer_value',v_integer_value,'boolean_value',v_boolean_value,'manual_grant_id',v_grant.id,
            'provenance',v_provenance);
        END $fn$
        """
    )
    op.execute(f"ALTER FUNCTION {_ENTITLEMENT} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_ENTITLEMENT} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_ENTITLEMENT} TO prospect_app")

    # Preserve existing tenant billing behaviour and extend only its safe
    # projection with the distinct manual-grant summary.
    op.execute(
        r"""
        DO $copy$
        DECLARE v_definition text;
        BEGIN
          SELECT pg_get_functiondef('app_private.tenant_stripe_billing_state()'::regprocedure) INTO v_definition;
          v_definition:=replace(v_definition,'FUNCTION app_private.tenant_stripe_billing_state()',
            'FUNCTION app_private.tenant_stripe_billing_state_without_manual()');
          EXECUTE v_definition;
        END $copy$
        """
    )
    op.execute(f"ALTER FUNCTION {_BILLING_STATE_BASE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_BILLING_STATE_BASE} FROM PUBLIC, prospect_app, prospect_worker")
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.tenant_stripe_billing_state() RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_base jsonb; v_org uuid:=app_private.current_organization_id(); v_manual jsonb;
        BEGIN
          v_base:=app_private.tenant_stripe_billing_state_without_manual();
          IF v_base IS NULL OR v_org IS NULL THEN RETURN v_base; END IF;
          SELECT jsonb_build_object('state',g.state,'plan_version_id',g.plan_version_id,'plan_code',p.code,
            'version_number',v.version_number,'currency',v.currency,'ends_at',g.ends_at) INTO v_manual
          FROM public.manual_billing_grants g JOIN public.plan_versions v ON v.id=g.plan_version_id
          JOIN public.plan_catalog p ON p.id=v.plan_id WHERE g.organization_id=v_org
            AND (g.state='pending_approval' OR (g.state='active' AND g.ends_at>clock_timestamp()))
          ORDER BY g.created_at DESC,g.id DESC LIMIT 1;
          RETURN v_base||jsonb_build_object('manual_grant',v_manual);
        END $fn$
        """
    )
    op.execute(f"ALTER FUNCTION {_BILLING_STATE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_BILLING_STATE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_BILLING_STATE} TO prospect_app")

    # Checkout remains possible only after a temporary access grant has been
    # revoked or expired. This prevents two competing entitlement sources.
    op.execute(
        r"""
        DO $copy$
        DECLARE v_definition text;
        BEGIN
          SELECT pg_get_functiondef(
            'app_private.prepare_stripe_sandbox_checkout_v2(uuid,uuid,text,text,timestamp with time zone)'::regprocedure
          ) INTO v_definition;
          v_definition:=replace(v_definition,'FUNCTION app_private.prepare_stripe_sandbox_checkout_v2(',
            'FUNCTION app_private.prepare_stripe_sandbox_checkout_without_manual(');
          EXECUTE v_definition;
        END $copy$
        """
    )
    op.execute(f"ALTER FUNCTION {_CHECKOUT_BASE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_CHECKOUT_BASE} FROM PUBLIC, prospect_app, prospect_worker")
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.prepare_stripe_sandbox_checkout_v2(
          p_command_id uuid,p_plan_version_id uuid,p_key_digest text,p_request_fingerprint text,p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_org uuid:=app_private.current_organization_id();
        BEGIN
          IF v_org IS NOT NULL AND EXISTS(SELECT 1 FROM public.manual_billing_grants
            WHERE organization_id=v_org AND (state='pending_approval' OR (state='active' AND ends_at>p_now))) THEN
            RETURN jsonb_build_object('code','billing_subscription_exists');
          END IF;
          RETURN app_private.prepare_stripe_sandbox_checkout_without_manual(
            p_command_id,p_plan_version_id,p_key_digest,p_request_fingerprint,p_now
          );
        END $fn$
        """
    )
    op.execute(f"ALTER FUNCTION {_CHECKOUT} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_CHECKOUT} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_CHECKOUT} TO prospect_app")

    _replace_platform_billing_functions()
    for signature in _MANUAL_FUNCTIONS:
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC, prospect_worker")
        if "manual_billing_grant_payload" not in signature:
            op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")


def _replace_platform_billing_functions() -> None:
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.list_platform_billing_organizations(
          p_after uuid,p_limit integer,p_state text,p_source text
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_payload jsonb;
        BEGIN
          IF v_actor IS NULL OR NOT EXISTS(
            SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin'
          ) THEN RAISE EXCEPTION 'platform_billing_forbidden' USING ERRCODE='42501'; END IF;
          IF p_limit IS NULL OR p_limit<1 OR p_limit>100
             OR (p_state IS NOT NULL AND p_state NOT IN ('pending_checkout','pending_approval','active','past_due',
               'grace_period','suspended','canceling','canceled','expired','revoked','none'))
             OR (p_source IS NOT NULL AND p_source NOT IN ('stripe','simulated','catalog_only','manual_grant','none')) THEN
            RAISE EXCEPTION 'platform_billing_invalid_filter' USING ERRCODE='22023';
          END IF;
          WITH rows AS (
            SELECT o.id,o.name,o.status AS organization_status,
              coalesce(s.plan_code,c.plan_code,g.plan_code) AS plan_code,
              coalesce(s.version_number,c.version_number,g.version_number) AS version_number,
              coalesce(s.currency,c.currency,g.currency) AS currency,s.subscription_state,c.contract_state,g.manual_grant_state,
              CASE WHEN s.provider IS NOT NULL THEN s.provider WHEN c.contract_state IS NOT NULL THEN 'catalog_only'
                WHEN g.id IS NOT NULL THEN 'manual_grant' ELSE 'none' END AS source,
              coalesce(s.current_period_end,g.ends_at) AS current_period_end,
              coalesce(s.cancel_at_period_end,false) AS cancel_at_period_end,
              CASE WHEN EXISTS(SELECT 1 FROM public.billing_reconciliation_differences d WHERE d.organization_id=o.id
                AND d.resolved_at IS NULL AND d.difference_code<>'in_sync') THEN 'needs_review' ELSE 'not_checked' END AS reconciliation_status
            FROM public.organizations o
            LEFT JOIN LATERAL (
              SELECT s.provider,s.currency,s.state AS subscription_state,s.current_period_end,s.cancel_at_period_end,
                p.code AS plan_code,v.version_number FROM public.subscriptions s
              JOIN public.plan_versions v ON v.id=s.plan_version_id JOIN public.plan_catalog p ON p.id=v.plan_id
              WHERE s.organization_id=o.id AND s.state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling')
              ORDER BY s.updated_at DESC,s.id DESC LIMIT 1
            ) s ON true
            LEFT JOIN LATERAL (
              SELECT c.state AS contract_state,c.currency,p.code AS plan_code,v.version_number
              FROM public.organization_plan_contracts c JOIN public.plan_versions v ON v.id=c.plan_version_id
              JOIN public.plan_catalog p ON p.id=v.plan_id WHERE c.organization_id=o.id
                AND c.state IN ('pending','active','suspended') ORDER BY c.updated_at DESC,c.id DESC LIMIT 1
            ) c ON true
            LEFT JOIN LATERAL (
              SELECT g.id,g.ends_at,CASE WHEN g.state='active' AND g.ends_at<=clock_timestamp() THEN 'expired' ELSE g.state END AS manual_grant_state,
                p.code AS plan_code,v.version_number,v.currency FROM public.manual_billing_grants g
              JOIN public.plan_versions v ON v.id=g.plan_version_id JOIN public.plan_catalog p ON p.id=v.plan_id
              WHERE g.organization_id=o.id ORDER BY g.created_at DESC,g.id DESC LIMIT 1
            ) g ON true WHERE p_after IS NULL OR o.id>p_after
          ), filtered AS (
            SELECT * FROM rows WHERE (p_state IS NULL OR coalesce(subscription_state,contract_state,manual_grant_state,'none')=p_state)
              AND (p_source IS NULL OR source=p_source) ORDER BY id LIMIT p_limit+1
          ), page AS (SELECT * FROM filtered LIMIT p_limit)
          SELECT jsonb_build_object('items',coalesce(jsonb_agg(jsonb_build_object(
            'id',id,'name',name,'organization_status',organization_status,'plan_code',plan_code,
            'version_number',version_number,'currency',currency,'subscription_state',subscription_state,
            'contract_state',contract_state,'manual_grant_state',manual_grant_state,'source',source,
            'current_period_end',current_period_end,'cancel_at_period_end',cancel_at_period_end,
            'reconciliation_status',reconciliation_status
          ) ORDER BY id),'[]'::jsonb),'next_cursor',(SELECT id::text FROM filtered ORDER BY id OFFSET p_limit LIMIT 1))
          INTO v_payload FROM page;
          RETURN v_payload;
        END $fn$
        """
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.get_platform_billing_organization(p_organization_id uuid)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_organization jsonb; v_grant jsonb;
        BEGIN
          IF v_actor IS NULL OR NOT EXISTS(
            SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin'
          ) THEN RAISE EXCEPTION 'platform_billing_forbidden' USING ERRCODE='42501'; END IF;
          IF p_organization_id IS NULL THEN RETURN NULL; END IF;
          SELECT item INTO v_organization FROM (
            SELECT jsonb_build_object(
              'id',o.id,'name',o.name,'organization_status',o.status,
              'plan_code',coalesce(s.plan_code,c.plan_code,g.plan_code),
              'version_number',coalesce(s.version_number,c.version_number,g.version_number),
              'currency',coalesce(s.currency,c.currency,g.currency),'subscription_state',s.subscription_state,
              'contract_state',c.contract_state,'manual_grant_state',g.manual_grant_state,
              'source',CASE WHEN s.provider IS NOT NULL THEN s.provider WHEN c.contract_state IS NOT NULL THEN 'catalog_only'
                WHEN g.id IS NOT NULL THEN 'manual_grant' ELSE 'none' END,
              'current_period_end',coalesce(s.current_period_end,g.ends_at),'cancel_at_period_end',coalesce(s.cancel_at_period_end,false),
              'reconciliation_status',CASE WHEN EXISTS(SELECT 1 FROM public.billing_reconciliation_differences d
                WHERE d.organization_id=o.id AND d.resolved_at IS NULL AND d.difference_code<>'in_sync') THEN 'needs_review' ELSE 'not_checked' END
            ) AS item FROM public.organizations o
            LEFT JOIN LATERAL (
              SELECT s.provider,s.currency,s.state AS subscription_state,s.current_period_end,s.cancel_at_period_end,
                p.code AS plan_code,v.version_number FROM public.subscriptions s JOIN public.plan_versions v ON v.id=s.plan_version_id
              JOIN public.plan_catalog p ON p.id=v.plan_id WHERE s.organization_id=o.id
                AND s.state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling') ORDER BY s.updated_at DESC,s.id DESC LIMIT 1
            ) s ON true
            LEFT JOIN LATERAL (
              SELECT c.state AS contract_state,c.currency,p.code AS plan_code,v.version_number FROM public.organization_plan_contracts c
              JOIN public.plan_versions v ON v.id=c.plan_version_id JOIN public.plan_catalog p ON p.id=v.plan_id
              WHERE c.organization_id=o.id AND c.state IN ('pending','active','suspended') ORDER BY c.updated_at DESC,c.id DESC LIMIT 1
            ) c ON true
            LEFT JOIN LATERAL (
              SELECT g.id,g.ends_at,CASE WHEN g.state='active' AND g.ends_at<=clock_timestamp() THEN 'expired' ELSE g.state END AS manual_grant_state,
                p.code AS plan_code,v.version_number,v.currency FROM public.manual_billing_grants g JOIN public.plan_versions v ON v.id=g.plan_version_id
              JOIN public.plan_catalog p ON p.id=v.plan_id WHERE g.organization_id=o.id ORDER BY g.created_at DESC,g.id DESC LIMIT 1
            ) g ON true WHERE o.id=p_organization_id
          ) detail;
          IF v_organization IS NULL THEN RETURN NULL; END IF;
          SELECT app_private.manual_billing_grant_payload(g.id,clock_timestamp()) INTO v_grant FROM public.manual_billing_grants g
          WHERE g.organization_id=p_organization_id ORDER BY g.created_at DESC,g.id DESC LIMIT 1;
          RETURN jsonb_build_object(
            'organization',v_organization,'manual_grant',v_grant,
            'events',coalesce((SELECT jsonb_agg(jsonb_build_object('event_type',event_type,'occurred_at',occurred_at) ORDER BY occurred_at DESC)
              FROM (SELECT event_type,occurred_at FROM public.billing_events WHERE organization_id=p_organization_id
                ORDER BY occurred_at DESC,id DESC LIMIT 20) events),'[]'::jsonb),
            'interventions',coalesce((SELECT jsonb_agg(jsonb_build_object('kind',kind,'status',status,
                'created_at',created_at,'updated_at',updated_at) ORDER BY created_at DESC) FROM (
              SELECT * FROM (
                SELECT command_kind AS kind,status,created_at,updated_at FROM public.billing_commands WHERE organization_id=p_organization_id
                UNION ALL SELECT 'manual_grant',CASE WHEN state='active' AND ends_at<=clock_timestamp() THEN 'expired' ELSE state END,
                  created_at,updated_at FROM public.manual_billing_grants WHERE organization_id=p_organization_id
              ) all_interventions ORDER BY created_at DESC LIMIT 20
            ) interventions),'[]'::jsonb)
          );
        END $fn$
        """
    )
    for signature in (
        "app_private.list_platform_billing_organizations(uuid,integer,text,text)",
        "app_private.get_platform_billing_organization(uuid)",
    ):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC, prospect_worker")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")


def downgrade() -> None:
    # Restore the original platform projection before the manual table disappears.
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.list_platform_billing_organizations(
          p_after uuid,p_limit integer,p_state text,p_source text
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_payload jsonb;
        BEGIN
          IF v_actor IS NULL OR NOT EXISTS(SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin') THEN RAISE EXCEPTION 'platform_billing_forbidden' USING ERRCODE='42501'; END IF;
          IF p_limit IS NULL OR p_limit<1 OR p_limit>100 OR (p_state IS NOT NULL AND p_state NOT IN ('pending_checkout','active','past_due','grace_period','suspended','canceling','canceled','none')) OR (p_source IS NOT NULL AND p_source NOT IN ('stripe','simulated','catalog_only','none')) THEN RAISE EXCEPTION 'platform_billing_invalid_filter' USING ERRCODE='22023'; END IF;
          WITH rows AS (
            SELECT o.id,o.name,o.status AS organization_status,coalesce(s.plan_code,c.plan_code) AS plan_code,coalesce(s.version_number,c.version_number) AS version_number,coalesce(s.currency,c.currency) AS currency,s.subscription_state,c.contract_state,coalesce(s.provider,CASE WHEN c.contract_state IS NULL THEN 'none' ELSE 'catalog_only' END) AS source,s.current_period_end,coalesce(s.cancel_at_period_end,false) AS cancel_at_period_end,CASE WHEN EXISTS(SELECT 1 FROM public.billing_reconciliation_differences d WHERE d.organization_id=o.id AND d.resolved_at IS NULL AND d.difference_code<>'in_sync') THEN 'needs_review' ELSE 'not_checked' END AS reconciliation_status
            FROM public.organizations o LEFT JOIN LATERAL (SELECT s.provider,s.currency,s.state AS subscription_state,s.current_period_end,s.cancel_at_period_end,p.code AS plan_code,v.version_number FROM public.subscriptions s JOIN public.plan_versions v ON v.id=s.plan_version_id JOIN public.plan_catalog p ON p.id=v.plan_id WHERE s.organization_id=o.id AND s.state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling') ORDER BY s.updated_at DESC,s.id DESC LIMIT 1) s ON true LEFT JOIN LATERAL (SELECT c.state AS contract_state,c.currency,p.code AS plan_code,v.version_number FROM public.organization_plan_contracts c JOIN public.plan_versions v ON v.id=c.plan_version_id JOIN public.plan_catalog p ON p.id=v.plan_id WHERE c.organization_id=o.id AND c.state IN ('pending','active','suspended') ORDER BY c.updated_at DESC,c.id DESC LIMIT 1) c ON true WHERE (p_after IS NULL OR o.id>p_after)
          ), filtered AS (SELECT * FROM rows WHERE (p_state IS NULL OR coalesce(subscription_state,contract_state,'none')=p_state) AND (p_source IS NULL OR source=p_source) ORDER BY id LIMIT p_limit+1), page AS (SELECT * FROM filtered LIMIT p_limit)
          SELECT jsonb_build_object('items',coalesce(jsonb_agg(jsonb_build_object('id',id,'name',name,'organization_status',organization_status,'plan_code',plan_code,'version_number',version_number,'currency',currency,'subscription_state',subscription_state,'contract_state',contract_state,'source',source,'current_period_end',current_period_end,'cancel_at_period_end',cancel_at_period_end,'reconciliation_status',reconciliation_status) ORDER BY id),'[]'::jsonb),'next_cursor',(SELECT id::text FROM filtered ORDER BY id OFFSET p_limit LIMIT 1)) INTO v_payload FROM page; RETURN v_payload;
        END $fn$
        """
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.get_platform_billing_organization(p_organization_id uuid)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_organization jsonb;
        BEGIN
          IF v_actor IS NULL OR NOT EXISTS(SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin') THEN RAISE EXCEPTION 'platform_billing_forbidden' USING ERRCODE='42501'; END IF;
          IF p_organization_id IS NULL THEN RETURN NULL; END IF;
          SELECT item INTO v_organization FROM (SELECT jsonb_build_object('id',o.id,'name',o.name,'organization_status',o.status,'plan_code',coalesce(s.plan_code,c.plan_code),'version_number',coalesce(s.version_number,c.version_number),'currency',coalesce(s.currency,c.currency),'subscription_state',s.subscription_state,'contract_state',c.contract_state,'source',coalesce(s.provider,CASE WHEN c.contract_state IS NULL THEN 'none' ELSE 'catalog_only' END),'current_period_end',s.current_period_end,'cancel_at_period_end',coalesce(s.cancel_at_period_end,false),'reconciliation_status',CASE WHEN EXISTS(SELECT 1 FROM public.billing_reconciliation_differences d WHERE d.organization_id=o.id AND d.resolved_at IS NULL AND d.difference_code<>'in_sync') THEN 'needs_review' ELSE 'not_checked' END) AS item FROM public.organizations o LEFT JOIN LATERAL (SELECT s.provider,s.currency,s.state AS subscription_state,s.current_period_end,s.cancel_at_period_end,p.code AS plan_code,v.version_number FROM public.subscriptions s JOIN public.plan_versions v ON v.id=s.plan_version_id JOIN public.plan_catalog p ON p.id=v.plan_id WHERE s.organization_id=o.id AND s.state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling') ORDER BY s.updated_at DESC,s.id DESC LIMIT 1) s ON true LEFT JOIN LATERAL (SELECT c.state AS contract_state,c.currency,p.code AS plan_code,v.version_number FROM public.organization_plan_contracts c JOIN public.plan_versions v ON v.id=c.plan_version_id JOIN public.plan_catalog p ON p.id=v.plan_id WHERE c.organization_id=o.id AND c.state IN ('pending','active','suspended') ORDER BY c.updated_at DESC,c.id DESC LIMIT 1) c ON true WHERE o.id=p_organization_id) detail;
          IF v_organization IS NULL THEN RETURN NULL; END IF;
          RETURN jsonb_build_object('organization',v_organization,'events',coalesce((SELECT jsonb_agg(jsonb_build_object('event_type',event_type,'occurred_at',occurred_at) ORDER BY occurred_at DESC) FROM (SELECT event_type,occurred_at FROM public.billing_events WHERE organization_id=p_organization_id ORDER BY occurred_at DESC,id DESC LIMIT 20) events),'[]'::jsonb),'interventions',coalesce((SELECT jsonb_agg(jsonb_build_object('kind',command_kind,'status',status,'created_at',created_at,'updated_at',updated_at) ORDER BY created_at DESC) FROM (SELECT command_kind,status,created_at,updated_at FROM public.billing_commands WHERE organization_id=p_organization_id ORDER BY created_at DESC,id DESC LIMIT 20) commands),'[]'::jsonb));
        END $fn$
        """
    )
    for signature in (
        "app_private.list_platform_billing_organizations(uuid,integer,text,text)",
        "app_private.get_platform_billing_organization(uuid)",
    ):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC, prospect_worker")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")

    for original, backup in (
        (_CHECKOUT, _CHECKOUT_BASE),
        (_BILLING_STATE, _BILLING_STATE_BASE),
        (_ENTITLEMENT, _ENTITLEMENT_CONTRACT),
    ):
        op.execute(
            f"""
            DO $restore$
            DECLARE v_definition text;
            BEGIN
              SELECT pg_get_functiondef('{backup}'::regprocedure) INTO v_definition;
              v_definition:=replace(v_definition,'FUNCTION {backup.split("(")[0]}(', 'FUNCTION {original.split("(")[0]}(');
              EXECUTE v_definition;
            END $restore$
            """
        )
    op.execute(f"ALTER FUNCTION {_ENTITLEMENT} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_ENTITLEMENT} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_ENTITLEMENT} TO prospect_app")
    op.execute(f"ALTER FUNCTION {_BILLING_STATE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_BILLING_STATE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_BILLING_STATE} TO prospect_app")
    op.execute(f"ALTER FUNCTION {_CHECKOUT} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_CHECKOUT} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_CHECKOUT} TO prospect_app")

    for signature in (_CHECKOUT_BASE, _BILLING_STATE_BASE, _ENTITLEMENT_CONTRACT):
        op.execute(f"DROP FUNCTION {signature}")
    for signature in reversed(_MANUAL_FUNCTIONS):
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("REVOKE SELECT ON public.manual_billing_grants FROM prospect_rls_definer")
    op.execute("DROP TABLE public.manual_billing_grant_operations")
    op.execute("DROP TABLE public.manual_billing_grants")
