"""Séparer le rôle Web et protéger les tables locataires avec RLS.

Revision ID: 20260723_0003
Revises: 20260723_0002
Create Date: 2026-07-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260723_0003"
down_revision: str | None = "20260723_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $migration_checks$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prospect_app') THEN
                RAISE EXCEPTION
                    'Le rôle prospect_app doit être provisionné avant la migration 20260723_0003.';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_roles
                WHERE rolname = 'prospect_rls_definer'
                  AND rolbypassrls
                  AND NOT rolcanlogin
                  AND NOT rolsuper
            ) THEN
                RAISE EXCEPTION
                    'Le rôle technique prospect_rls_definer est absent ou incorrectement configuré.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM pg_roles
                WHERE rolname = 'prospect_app'
                  AND (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolinherit OR NOT rolcanlogin)
            ) THEN
                RAISE EXCEPTION 'Le rôle prospect_app possède un attribut PostgreSQL interdit.';
            END IF;

            IF pg_has_role('prospect_app', current_user, 'MEMBER') THEN
                RAISE EXCEPTION 'Le rôle prospect_app ne doit pas être membre du rôle propriétaire.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM pg_roles AS granted_role
                WHERE granted_role.rolname <> 'prospect_app'
                  AND (granted_role.rolsuper OR granted_role.rolbypassrls)
                  AND pg_has_role('prospect_app', granted_role.oid, 'MEMBER')
            ) THEN
                RAISE EXCEPTION 'Le rôle prospect_app appartient à un rôle privilégié interdit.';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM pg_class AS relation
                WHERE relation.relname IN ('organizations', 'memberships', 'user_invitations')
                  AND pg_has_role('prospect_app', relation.relowner, 'MEMBER')
            ) THEN
                RAISE EXCEPTION
                    'Le rôle prospect_app ne doit posséder aucune table locataire ni appartenir à son propriétaire.';
            END IF;
        END
        $migration_checks$;
        """
    )

    op.execute("CREATE SCHEMA app_private")
    op.execute("REVOKE ALL ON SCHEMA app_private FROM PUBLIC")
    op.execute("GRANT USAGE, CREATE ON SCHEMA app_private TO prospect_rls_definer")

    op.execute(
        """
        CREATE FUNCTION app_private.current_actor_id()
        RETURNS uuid
        LANGUAGE plpgsql
        STABLE
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            raw_value text;
        BEGIN
            raw_value := current_setting('app.actor_id', true);
            IF raw_value IS NULL OR raw_value = '' THEN
                RETURN NULL;
            END IF;
            RETURN raw_value::uuid;
        EXCEPTION
            WHEN invalid_text_representation THEN
                RETURN NULL;
        END
        $function$;
        """
    )
    op.execute("ALTER FUNCTION app_private.current_actor_id() OWNER TO prospect_rls_definer")

    op.execute(
        """
        CREATE FUNCTION app_private.current_organization_id()
        RETURNS uuid
        LANGUAGE plpgsql
        STABLE
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            raw_value text;
        BEGIN
            raw_value := current_setting('app.organization_id', true);
            IF raw_value IS NULL OR raw_value = '' THEN
                RETURN NULL;
            END IF;
            RETURN raw_value::uuid;
        EXCEPTION
            WHEN invalid_text_representation THEN
                RETURN NULL;
        END
        $function$;
        """
    )
    op.execute("ALTER FUNCTION app_private.current_organization_id() OWNER TO prospect_rls_definer")

    op.execute(
        """
        CREATE FUNCTION app_private.identity_memberships()
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
    op.execute("REVOKE CREATE ON SCHEMA app_private FROM prospect_rls_definer")

    op.execute("REVOKE ALL ON FUNCTION app_private.current_actor_id() FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION app_private.current_organization_id() FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION app_private.identity_memberships() FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA app_private TO prospect_app")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.current_organization_id() TO prospect_app")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.identity_memberships() TO prospect_app")

    op.execute("GRANT USAGE ON SCHEMA public TO prospect_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.users TO prospect_app")
    op.execute("GRANT SELECT, UPDATE ON TABLE public.organizations TO prospect_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.memberships TO prospect_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.user_invitations TO prospect_app")
    op.execute("GRANT SELECT ON TABLE public.organizations, public.memberships TO prospect_rls_definer")

    op.execute("ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.organizations FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.memberships FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.user_invitations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.user_invitations FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY organizations_tenant_isolation
        ON public.organizations
        FOR ALL
        TO prospect_app
        USING (id = app_private.current_organization_id())
        WITH CHECK (id = app_private.current_organization_id())
        """
    )
    op.execute(
        """
        CREATE POLICY memberships_tenant_isolation
        ON public.memberships
        FOR ALL
        TO prospect_app
        USING (organization_id = app_private.current_organization_id())
        WITH CHECK (organization_id = app_private.current_organization_id())
        """
    )
    op.execute(
        """
        CREATE POLICY user_invitations_tenant_isolation
        ON public.user_invitations
        FOR ALL
        TO prospect_app
        USING (organization_id = app_private.current_organization_id())
        WITH CHECK (organization_id = app_private.current_organization_id())
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY user_invitations_tenant_isolation ON public.user_invitations")
    op.execute("DROP POLICY memberships_tenant_isolation ON public.memberships")
    op.execute("DROP POLICY organizations_tenant_isolation ON public.organizations")

    op.execute("ALTER TABLE public.user_invitations NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.user_invitations DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.memberships NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.memberships DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.organizations NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.organizations DISABLE ROW LEVEL SECURITY")

    op.execute("REVOKE ALL ON TABLE public.user_invitations FROM prospect_app")
    op.execute("REVOKE ALL ON TABLE public.memberships FROM prospect_app")
    op.execute("REVOKE ALL ON TABLE public.organizations FROM prospect_app")
    op.execute("REVOKE ALL ON TABLE public.users FROM prospect_app")
    op.execute("REVOKE SELECT ON TABLE public.organizations, public.memberships FROM prospect_rls_definer")
    op.execute("REVOKE USAGE ON SCHEMA public FROM prospect_app")
    op.execute("DROP SCHEMA app_private CASCADE")
