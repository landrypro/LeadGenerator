"""Expose la langue et le fuseau horaire dans les résumés de session.

Revision ID: 20260922_0021
Revises: 20260910_0020
Create Date: 2026-09-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260922_0021"
down_revision: str | None = "20260910_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL ne permet pas de modifier les paramètres OUT d'une fonction
    # existante avec CREATE OR REPLACE. La migration est transactionnelle : la
    # fonction n'est donc jamais absente après un échec ou après le commit.
    op.execute("DROP FUNCTION app_private.identity_memberships()")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_private.identity_memberships()
        RETURNS TABLE (
            membership_id uuid,
            organization_id uuid,
            organization_name text,
            membership_role text,
            membership_status text,
            organization_status text,
            membership_created_at timestamp with time zone,
            organization_locale text,
            organization_timezone text
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $function$
            SELECT
                membership.id,
                membership.organization_id,
                organization.name::text,
                membership.role::text,
                membership.status::text,
                organization.status::text,
                membership.created_at,
                organization.locale::text,
                organization.timezone::text
            FROM public.memberships AS membership
            JOIN public.organizations AS organization
              ON organization.id = membership.organization_id
            WHERE membership.user_id = app_private.current_actor_id()
            ORDER BY membership.created_at, membership.id
        $function$;
        """
    )
    op.execute("ALTER FUNCTION app_private.identity_memberships() OWNER TO prospect_rls_definer")
    # CREATE FUNCTION rétablit le privilège EXECUTE implicite de PUBLIC. Le
    # contrat RLS impose que seul le rôle applicatif puisse appeler cette
    # fonction SECURITY DEFINER.
    op.execute("REVOKE ALL ON FUNCTION app_private.identity_memberships() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.identity_memberships() TO prospect_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION app_private.identity_memberships()")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_private.identity_memberships()
        RETURNS TABLE (
            membership_id uuid,
            organization_id uuid,
            organization_name text,
            membership_role text,
            membership_status text,
            organization_status text,
            membership_created_at timestamp with time zone
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $function$
            SELECT
                membership.id,
                membership.organization_id,
                organization.name::text,
                membership.role::text,
                membership.status::text,
                organization.status::text,
                membership.created_at
            FROM public.memberships AS membership
            JOIN public.organizations AS organization
              ON organization.id = membership.organization_id
            WHERE membership.user_id = app_private.current_actor_id()
            ORDER BY membership.created_at, membership.id
        $function$;
        """
    )
    op.execute("ALTER FUNCTION app_private.identity_memberships() OWNER TO prospect_rls_definer")
    op.execute("REVOKE ALL ON FUNCTION app_private.identity_memberships() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.identity_memberships() TO prospect_app")
