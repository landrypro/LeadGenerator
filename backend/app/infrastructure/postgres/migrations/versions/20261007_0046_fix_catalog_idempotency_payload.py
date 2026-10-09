"""Keep execution timestamps while excluding them from catalog replay hashes."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261007_0046"
down_revision: str | Sequence[str] | None = "20261007_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WRAPPER = "app_private.platform_catalog_mutate(text,jsonb)"


def upgrade() -> None:
    op.execute(r"""
      CREATE OR REPLACE FUNCTION app_private.platform_catalog_mutate(p_command text,p_payload jsonb)
      RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $f$
      DECLARE
        v_actor uuid:=app_private.current_actor_id(); v_operation uuid; v_fingerprint jsonb; v_existing public.catalog_mutation_operations%ROWTYPE; v_result jsonb;
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
      END $f$;
    """)
    op.execute(f"ALTER FUNCTION {_WRAPPER} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_WRAPPER} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_WRAPPER} TO prospect_app")


def downgrade() -> None:
    # Revision 0045 contains the same wrapper contract.  It is left in place
    # on downgrade because this repair only changes the function body.
    pass
