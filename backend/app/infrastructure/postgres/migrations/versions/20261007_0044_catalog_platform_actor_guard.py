"""Guard P52-03 catalog commands at the database boundary."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261007_0044"
down_revision: str | Sequence[str] | None = "20261007_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLAN = "app_private.platform_create_catalog_plan(uuid,text,integer,timestamp with time zone)"
_VERSION = "app_private.platform_create_catalog_version(uuid,uuid,integer,text,text,bigint,timestamp with time zone,timestamp with time zone,jsonb,timestamp with time zone)"
_PUBLISH = "app_private.platform_publish_catalog_version(uuid,integer,timestamp with time zone)"
_ATTACH = "app_private.platform_attach_catalog_contract(uuid,uuid,uuid,text,timestamp with time zone,timestamp with time zone,timestamp with time zone)"
_STATE = "app_private.platform_change_catalog_contract_state(uuid,integer,text,timestamp with time zone)"
_WRAPPER = "app_private.platform_catalog_mutate(text,jsonb)"


def upgrade() -> None:
    # The primitive functions remain private implementation details.  The
    # only app-role entry point checks the persisted platform role itself,
    # independently from a caller supplied capability boolean.
    for signature in (_PLAN, _VERSION, _PUBLISH, _ATTACH, _STATE):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM prospect_app")
    op.execute(r"""
      CREATE FUNCTION app_private.platform_catalog_mutate(p_command text,p_payload jsonb)
      RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $f$
      BEGIN
        IF NOT app_private.is_platform_actor() THEN
          RAISE EXCEPTION 'platform capability required' USING ERRCODE='42501';
        END IF;
        CASE p_command
          WHEN 'create_plan' THEN RETURN app_private.platform_create_catalog_plan(
            (p_payload->>'id')::uuid,p_payload->>'code',(p_payload->>'display_order')::integer,(p_payload->>'now')::timestamptz);
          WHEN 'create_plan_version' THEN RETURN app_private.platform_create_catalog_version(
            (p_payload->>'id')::uuid,(p_payload->>'plan_id')::uuid,(p_payload->>'version_number')::integer,
            p_payload->>'currency',p_payload->>'billing_cycle',(p_payload->>'amount')::bigint,
            (p_payload->>'effective_from')::timestamptz,NULLIF(p_payload->>'effective_until','')::timestamptz,
            p_payload->'entitlements',(p_payload->>'now')::timestamptz);
          WHEN 'publish_plan_version' THEN RETURN app_private.platform_publish_catalog_version(
            (p_payload->>'id')::uuid,(p_payload->>'expected_version')::integer,(p_payload->>'now')::timestamptz);
          WHEN 'attach_contract' THEN RETURN app_private.platform_attach_catalog_contract(
            (p_payload->>'id')::uuid,(p_payload->>'organization_id')::uuid,(p_payload->>'plan_version_id')::uuid,
            p_payload->>'state',(p_payload->>'effective_from')::timestamptz,NULLIF(p_payload->>'effective_until','')::timestamptz,(p_payload->>'now')::timestamptz);
          WHEN 'change_contract_state' THEN RETURN app_private.platform_change_catalog_contract_state(
            (p_payload->>'id')::uuid,(p_payload->>'expected_version')::integer,p_payload->>'state',(p_payload->>'now')::timestamptz);
          ELSE RAISE EXCEPTION 'unknown catalog command' USING ERRCODE='22023';
        END CASE;
      END $f$;
    """)
    op.execute(f"ALTER FUNCTION {_WRAPPER} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_WRAPPER} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_WRAPPER} TO prospect_app")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_WRAPPER} FROM prospect_app")
    op.execute(f"DROP FUNCTION {_WRAPPER}")
    for signature in (_PLAN, _VERSION, _PUBLISH, _ATTACH, _STATE):
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")
