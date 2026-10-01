"""Fix the audit trigger call made when a Meta ingestion is admitted.

Revision ID: 20260929_0028
Revises: 20260929_0027
"""

from alembic import op

revision = "20260929_0028"
down_revision = "20260929_0027"
branch_labels = None
depends_on = None

_FUNCTION_SIGNATURE = "app_private.capture_connector_ingestion_audit()"


def _create_audit_trigger_function(*, typed_schema_version: bool) -> None:
    schema_version = "1::smallint" if typed_schema_version else "1"
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {_FUNCTION_SIGNATURE} RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, app_private AS $$
        DECLARE v_action text; v_result text; v_source text;
        BEGIN
          IF TG_OP = 'INSERT' THEN
            v_action := 'connector.ingestion_admitted'; v_result := NULL; v_source := 'api';
          ELSIF NEW.status IS NOT DISTINCT FROM OLD.status OR NEW.status NOT IN ('succeeded','quarantined','failed','revoked') THEN
            RETURN NEW;
          ELSE
            v_action := 'connector.ingestion_completed'; v_source := 'worker';
            v_result := CASE NEW.status WHEN 'succeeded' THEN 'imported' WHEN 'quarantined' THEN 'quarantined'
              WHEN 'failed' THEN 'failed' ELSE 'authorization_revoked' END;
          END IF;
          PERFORM app_private.append_audit_event(
            gen_random_uuid(), 'tenant'::text, NEW.organization_id, 'user'::text, NEW.actor_user_id, v_action,
            'connector_ingestion'::text, NEW.id, pg_catalog.current_setting('app.request_id', true)::text,
            pg_catalog.current_setting('app.request_id', true)::text, v_source,
            CASE WHEN v_result IS NULL THEN jsonb_build_object('status', NEW.status)
                 ELSE jsonb_build_object('status', NEW.status, 'result_code', v_result) END, {schema_version});
          RETURN NEW;
        END $$
        """
    )
    op.execute(f"ALTER FUNCTION {_FUNCTION_SIGNATURE} OWNER TO prospect_rls_definer")


def upgrade() -> None:
    # append_audit_event expects its final argument as smallint. PostgreSQL does
    # not implicitly narrow the integer literal used by the original trigger.
    _create_audit_trigger_function(typed_schema_version=True)


def downgrade() -> None:
    _create_audit_trigger_function(typed_schema_version=False)
