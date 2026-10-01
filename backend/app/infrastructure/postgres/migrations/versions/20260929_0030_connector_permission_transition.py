"""Apply connector declarations to trigger-created contact permissions.

Revision ID: 20260929_0030
Revises: 20260929_0029
"""

from collections.abc import Sequence

from alembic import op

revision = "20260929_0030"
down_revision = "20260929_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FUNCTION_SIGNATURE = (
    "app_private.set_connector_contact_permission(uuid, character varying, uuid, timestamp with time zone)"
)


def upgrade() -> None:
    # The normal contact-channel trigger inserts one `unknown` permission.  This
    # definer function lets the connector worker transition only that row and
    # only when the channel belongs to the current tenant, actor and provenance.
    op.execute("GRANT SELECT ON TABLE public.contact_channels TO prospect_rls_definer")
    op.execute("GRANT UPDATE ON TABLE public.contact_permissions TO prospect_rls_definer")
    op.execute("""
        CREATE FUNCTION app_private.set_connector_contact_permission(
            p_channel_id uuid,
            p_status character varying,
            p_provenance_id uuid,
            p_decided_at timestamp with time zone
        ) RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public, app_private
        AS $function$
        DECLARE
            v_organization_id uuid := app_private.current_organization_id();
            v_actor_id uuid := app_private.current_actor_id();
            v_updated integer;
        BEGIN
            IF p_status NOT IN ('unknown', 'allowed') OR p_decided_at IS NULL THEN
                RAISE EXCEPTION 'invalid_connector_permission';
            END IF;

            UPDATE public.contact_permissions AS permission
            SET status = p_status,
                legal_basis_code = CASE WHEN p_status = 'allowed' THEN 'consent' ELSE NULL END,
                provenance_id = p_provenance_id,
                decided_at = p_decided_at,
                decided_by = v_actor_id,
                valid_from = p_decided_at,
                updated_at = p_decided_at,
                version = permission.version + 1
            FROM public.contact_channels AS channel
            WHERE permission.organization_id = v_organization_id
              AND permission.channel_id = p_channel_id
              AND permission.status = 'unknown'
              AND permission.provenance_id IS NULL
              AND channel.organization_id = v_organization_id
              AND channel.id = p_channel_id
              AND channel.provenance_id = p_provenance_id
              AND channel.created_by = v_actor_id;

            GET DIAGNOSTICS v_updated = ROW_COUNT;
            IF v_updated <> 1 THEN
                RAISE EXCEPTION 'invalid_connector_permission_transition';
            END IF;
        END
        $function$
    """)
    op.execute(f"ALTER FUNCTION {_FUNCTION_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_FUNCTION_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_FUNCTION_SIGNATURE} TO prospect_worker")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {_FUNCTION_SIGNATURE}")
    op.execute("REVOKE UPDATE ON TABLE public.contact_permissions FROM prospect_rls_definer")
