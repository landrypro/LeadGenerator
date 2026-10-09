"""Add auditable, dual-control mutations for P52 contract overrides.

Revision ID: 20261008_0050
Revises: 20261008_0049
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261008_0050"
down_revision: str | Sequence[str] | None = "20261008_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_WRAPPER = "app_private.platform_catalog_mutate(text,jsonb)"
_OVERRIDE_FUNCTIONS = (
    "app_private.platform_propose_catalog_contract_override(uuid,uuid,text,text,bigint,boolean,text,timestamptz,timestamptz,timestamptz)",
    "app_private.platform_approve_catalog_contract_override(uuid,integer,timestamptz)",
    "app_private.platform_revoke_catalog_contract_override(uuid,integer,timestamptz)",
)


def _override_json(prefix: str = "v_override") -> str:
    return (
        "jsonb_build_object('id',"
        f"{prefix}.id,'organization_id',{prefix}.organization_id,'contract_id',{prefix}.contract_id,"
        f"'entitlement_key',{prefix}.entitlement_key,'value_kind',{prefix}.value_kind,"
        f"'integer_value',{prefix}.integer_value,'boolean_value',{prefix}.boolean_value,'state',{prefix}.state,"
        f"'requested_by_user_id',{prefix}.requested_by_user_id,'approved_by_user_id',{prefix}.approved_by_user_id,"
        f"'starts_at',{prefix}.starts_at,'ends_at',{prefix}.ends_at,'version',{prefix}.version)"
    )


def upgrade() -> None:
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.plan_contract_overrides TO prospect_rls_definer")
    op.execute("ALTER TABLE public.catalog_mutation_operations DROP CONSTRAINT ck_catalog_mutation_operations_command")
    op.execute(
        """
        ALTER TABLE public.catalog_mutation_operations
        ADD CONSTRAINT ck_catalog_mutation_operations_command CHECK (command IN (
          'create_plan','create_plan_version','publish_plan_version','attach_contract','change_contract_state',
          'propose_contract_override','approve_contract_override','revoke_contract_override'
        ))
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION app_private.platform_propose_catalog_contract_override(
          p_id uuid, p_contract_id uuid, p_entitlement_key text, p_value_kind text,
          p_integer_value bigint, p_boolean_value boolean, p_justification text,
          p_starts_at timestamptz, p_ends_at timestamptz, p_now timestamptz
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_actor uuid := app_private.current_actor_id();
          v_contract public.organization_plan_contracts%ROWTYPE;
          v_entitlement public.plan_entitlements%ROWTYPE;
          v_override public.plan_contract_overrides%ROWTYPE;
        BEGIN
          IF v_actor IS NULL OR p_now IS NULL OR p_ends_at <= p_starts_at OR p_ends_at <= p_now
            OR char_length(btrim(COALESCE(p_justification,''))) NOT BETWEEN 1 AND 512 THEN
            RETURN jsonb_build_object('code','invalid_contract');
          END IF;
          SELECT * INTO v_contract FROM public.organization_plan_contracts
          WHERE id=p_contract_id AND state IN ('pending','active') FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','not_found'); END IF;
          SELECT * INTO v_entitlement FROM public.plan_entitlements
          WHERE plan_version_id=v_contract.plan_version_id AND entitlement_key=p_entitlement_key;
          IF NOT FOUND OR v_entitlement.value_kind<>p_value_kind
            OR (p_value_kind='limit' AND (p_integer_value IS NULL OR p_integer_value<0 OR p_boolean_value IS NOT NULL))
            OR (p_value_kind='switch' AND (p_boolean_value IS NULL OR p_integer_value IS NOT NULL)) THEN
            RETURN jsonb_build_object('code','invalid_contract');
          END IF;
          INSERT INTO public.plan_contract_overrides(
            id,organization_id,contract_id,entitlement_key,value_kind,integer_value,boolean_value,state,justification,
            requested_by_user_id,starts_at,ends_at,created_at,updated_at,version
          ) VALUES (
            p_id,v_contract.organization_id,p_contract_id,p_entitlement_key,p_value_kind,p_integer_value,p_boolean_value,
            'pending_approval',btrim(p_justification),v_actor,p_starts_at,p_ends_at,p_now,p_now,1
          ) RETURNING * INTO v_override;
          RETURN jsonb_build_object('code','created','contract_override',{_override_json()});
        END $fn$;
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION app_private.platform_approve_catalog_contract_override(
          p_id uuid, p_expected_version integer, p_now timestamptz
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_actor uuid := app_private.current_actor_id();
          v_override public.plan_contract_overrides%ROWTYPE;
          v_safety public.entitlement_safety_ceilings%ROWTYPE;
        BEGIN
          SELECT * INTO v_override FROM public.plan_contract_overrides WHERE id=p_id FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','not_found'); END IF;
          IF p_expected_version<>v_override.version THEN
            RETURN jsonb_build_object('code','version_conflict','current_version',v_override.version);
          END IF;
          IF v_override.state<>'pending_approval' OR v_actor IS NULL OR v_actor=v_override.requested_by_user_id
            OR p_now IS NULL OR p_now>=v_override.ends_at THEN
            RETURN jsonb_build_object('code',CASE WHEN v_actor=v_override.requested_by_user_id THEN 'approval_required' ELSE 'invalid_transition' END);
          END IF;
          SELECT * INTO v_safety FROM public.entitlement_safety_ceilings
          WHERE entitlement_key=v_override.entitlement_key;
          IF FOUND AND (
            v_safety.value_kind<>v_override.value_kind
            OR (v_override.value_kind='limit' AND v_override.integer_value>v_safety.integer_value)
            OR (v_override.value_kind='switch' AND v_override.boolean_value AND NOT v_safety.boolean_value)
          ) THEN
            RETURN jsonb_build_object('code','safety_ceiling_exceeded');
          END IF;
          UPDATE public.plan_contract_overrides
          SET state='active',approved_by_user_id=v_actor,updated_at=p_now,version=version+1
          WHERE id=p_id RETURNING * INTO v_override;
          RETURN jsonb_build_object('code','updated','contract_override',{_override_json()});
        END $fn$;
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION app_private.platform_revoke_catalog_contract_override(
          p_id uuid, p_expected_version integer, p_now timestamptz
        ) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_override public.plan_contract_overrides%ROWTYPE;
        BEGIN
          SELECT * INTO v_override FROM public.plan_contract_overrides WHERE id=p_id FOR UPDATE;
          IF NOT FOUND THEN RETURN jsonb_build_object('code','not_found'); END IF;
          IF p_expected_version<>v_override.version THEN
            RETURN jsonb_build_object('code','version_conflict','current_version',v_override.version);
          END IF;
          IF v_override.state NOT IN ('pending_approval','active') OR p_now IS NULL THEN
            RETURN jsonb_build_object('code','invalid_transition');
          END IF;
          UPDATE public.plan_contract_overrides
          SET state='revoked',updated_at=p_now,version=version+1
          WHERE id=p_id RETURNING * INTO v_override;
          RETURN jsonb_build_object('code','updated','contract_override',{_override_json()});
        END $fn$;
        """
    )
    for function in _OVERRIDE_FUNCTIONS:
        op.execute(f"ALTER FUNCTION {function} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_private.platform_catalog_mutate(p_command text,p_payload jsonb)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_actor uuid:=app_private.current_actor_id(); v_operation uuid; v_fingerprint jsonb;
          v_existing public.catalog_mutation_operations%ROWTYPE; v_result jsonb;
        BEGIN
          IF NOT app_private.is_platform_actor() THEN RAISE EXCEPTION 'platform capability required' USING ERRCODE='42501'; END IF;
          v_operation:=NULLIF(p_payload->>'operation_id','')::uuid;
          IF v_operation IS NULL THEN RAISE EXCEPTION 'catalog operation id required' USING ERRCODE='22023'; END IF;
          v_fingerprint:=p_payload-'operation_id'-'now';
          INSERT INTO public.catalog_mutation_operations(operation_id,actor_id,command,payload,response)
          VALUES(v_operation,v_actor,p_command,v_fingerprint,NULL) ON CONFLICT(operation_id) DO NOTHING;
          IF NOT FOUND THEN
            SELECT * INTO v_existing FROM public.catalog_mutation_operations WHERE operation_id=v_operation FOR UPDATE;
            IF v_existing.actor_id<>v_actor OR v_existing.command<>p_command OR v_existing.payload IS DISTINCT FROM v_fingerprint THEN
              RETURN jsonb_build_object('code','conflict');
            END IF;
            IF v_existing.response IS NULL THEN RAISE EXCEPTION 'catalog operation outcome unavailable' USING ERRCODE='P0001'; END IF;
            RETURN jsonb_set(v_existing.response,'{code}','"replayed"'::jsonb);
          END IF;
          CASE p_command
            WHEN 'create_plan' THEN v_result:=app_private.platform_create_catalog_plan((p_payload->>'id')::uuid,p_payload->>'code',(p_payload->>'display_order')::integer,(p_payload->>'now')::timestamptz);
            WHEN 'create_plan_version' THEN v_result:=app_private.platform_create_catalog_version((p_payload->>'id')::uuid,(p_payload->>'plan_id')::uuid,(p_payload->>'version_number')::integer,p_payload->>'currency',p_payload->>'billing_cycle',(p_payload->>'amount')::bigint,(p_payload->>'effective_from')::timestamptz,NULLIF(p_payload->>'effective_until','')::timestamptz,p_payload->'entitlements',(p_payload->>'now')::timestamptz);
            WHEN 'publish_plan_version' THEN v_result:=app_private.platform_publish_catalog_version((p_payload->>'id')::uuid,(p_payload->>'expected_version')::integer,(p_payload->>'now')::timestamptz);
            WHEN 'attach_contract' THEN v_result:=app_private.platform_attach_catalog_contract((p_payload->>'id')::uuid,(p_payload->>'organization_id')::uuid,(p_payload->>'plan_version_id')::uuid,p_payload->>'state',(p_payload->>'effective_from')::timestamptz,NULLIF(p_payload->>'effective_until','')::timestamptz,(p_payload->>'now')::timestamptz);
            WHEN 'change_contract_state' THEN v_result:=app_private.platform_change_catalog_contract_state((p_payload->>'id')::uuid,(p_payload->>'expected_version')::integer,p_payload->>'state',(p_payload->>'now')::timestamptz);
            WHEN 'propose_contract_override' THEN v_result:=app_private.platform_propose_catalog_contract_override((p_payload->>'id')::uuid,(p_payload->>'contract_id')::uuid,p_payload->>'entitlement_key',p_payload->>'value_kind',NULLIF(p_payload->>'integer_value','')::bigint,(p_payload->>'boolean_value')::boolean,p_payload->>'justification',(p_payload->>'starts_at')::timestamptz,(p_payload->>'ends_at')::timestamptz,(p_payload->>'now')::timestamptz);
            WHEN 'approve_contract_override' THEN v_result:=app_private.platform_approve_catalog_contract_override((p_payload->>'id')::uuid,(p_payload->>'expected_version')::integer,(p_payload->>'now')::timestamptz);
            WHEN 'revoke_contract_override' THEN v_result:=app_private.platform_revoke_catalog_contract_override((p_payload->>'id')::uuid,(p_payload->>'expected_version')::integer,(p_payload->>'now')::timestamptz);
            ELSE RAISE EXCEPTION 'unknown catalog command' USING ERRCODE='22023';
          END CASE;
          IF v_result->>'code' NOT IN ('created','published','updated') THEN
            DELETE FROM public.catalog_mutation_operations WHERE operation_id=v_operation;
            RETURN v_result;
          END IF;
          UPDATE public.catalog_mutation_operations SET response=v_result WHERE operation_id=v_operation;
          RETURN v_result;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_WRAPPER} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_WRAPPER} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_WRAPPER} TO prospect_app")


def downgrade() -> None:
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION app_private.platform_catalog_mutate(p_command text,p_payload jsonb)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_actor uuid:=app_private.current_actor_id(); v_operation uuid; v_fingerprint jsonb;
          v_existing public.catalog_mutation_operations%ROWTYPE; v_result jsonb;
        BEGIN
          IF NOT app_private.is_platform_actor() THEN RAISE EXCEPTION 'platform capability required' USING ERRCODE='42501'; END IF;
          v_operation:=NULLIF(p_payload->>'operation_id','')::uuid;
          IF v_operation IS NULL THEN RAISE EXCEPTION 'catalog operation id required' USING ERRCODE='22023'; END IF;
          v_fingerprint:=p_payload-'operation_id'-'now';
          INSERT INTO public.catalog_mutation_operations(operation_id,actor_id,command,payload,response)
          VALUES(v_operation,v_actor,p_command,v_fingerprint,NULL) ON CONFLICT(operation_id) DO NOTHING;
          IF NOT FOUND THEN
            SELECT * INTO v_existing FROM public.catalog_mutation_operations WHERE operation_id=v_operation FOR UPDATE;
            IF v_existing.actor_id<>v_actor OR v_existing.command<>p_command OR v_existing.payload IS DISTINCT FROM v_fingerprint THEN
              RETURN jsonb_build_object('code','conflict');
            END IF;
            IF v_existing.response IS NULL THEN RAISE EXCEPTION 'catalog operation outcome unavailable' USING ERRCODE='P0001'; END IF;
            RETURN jsonb_set(v_existing.response,'{code}','"replayed"'::jsonb);
          END IF;
          CASE p_command
            WHEN 'create_plan' THEN v_result:=app_private.platform_create_catalog_plan((p_payload->>'id')::uuid,p_payload->>'code',(p_payload->>'display_order')::integer,(p_payload->>'now')::timestamptz);
            WHEN 'create_plan_version' THEN v_result:=app_private.platform_create_catalog_version((p_payload->>'id')::uuid,(p_payload->>'plan_id')::uuid,(p_payload->>'version_number')::integer,p_payload->>'currency',p_payload->>'billing_cycle',(p_payload->>'amount')::bigint,(p_payload->>'effective_from')::timestamptz,NULLIF(p_payload->>'effective_until','')::timestamptz,p_payload->'entitlements',(p_payload->>'now')::timestamptz);
            WHEN 'publish_plan_version' THEN v_result:=app_private.platform_publish_catalog_version((p_payload->>'id')::uuid,(p_payload->>'expected_version')::integer,(p_payload->>'now')::timestamptz);
            WHEN 'attach_contract' THEN v_result:=app_private.platform_attach_catalog_contract((p_payload->>'id')::uuid,(p_payload->>'organization_id')::uuid,(p_payload->>'plan_version_id')::uuid,p_payload->>'state',(p_payload->>'effective_from')::timestamptz,NULLIF(p_payload->>'effective_until','')::timestamptz,(p_payload->>'now')::timestamptz);
            WHEN 'change_contract_state' THEN v_result:=app_private.platform_change_catalog_contract_state((p_payload->>'id')::uuid,(p_payload->>'expected_version')::integer,p_payload->>'state',(p_payload->>'now')::timestamptz);
            ELSE RAISE EXCEPTION 'unknown catalog command' USING ERRCODE='22023';
          END CASE;
          IF v_result->>'code' NOT IN ('created','published','updated') THEN
            DELETE FROM public.catalog_mutation_operations WHERE operation_id=v_operation;
            RETURN v_result;
          END IF;
          UPDATE public.catalog_mutation_operations SET response=v_result WHERE operation_id=v_operation;
          RETURN v_result;
        END $fn$;
        """
    )
    for function in _OVERRIDE_FUNCTIONS:
        op.execute(f"DROP FUNCTION {function}")
    op.execute("ALTER TABLE public.catalog_mutation_operations DROP CONSTRAINT ck_catalog_mutation_operations_command")
    op.execute(
        """
        ALTER TABLE public.catalog_mutation_operations
        ADD CONSTRAINT ck_catalog_mutation_operations_command CHECK (command IN (
          'create_plan','create_plan_version','publish_plan_version','attach_contract','change_contract_state'
        ))
        """
    )
    op.execute("REVOKE SELECT, INSERT, UPDATE ON public.plan_contract_overrides FROM prospect_rls_definer")
