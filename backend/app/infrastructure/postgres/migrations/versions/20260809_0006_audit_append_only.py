"""Créer le journal d audit append-only de l incrément 2.4.1.

Revision ID: 20260809_0006
Revises: 20260802_0005
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260809_0006"
down_revision: str | None = "20260802_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APPEND_SIGNATURE = (
    "app_private.append_audit_event(uuid, text, uuid, text, uuid, text, text, uuid, text, text, text, jsonb, smallint)"
)


def upgrade() -> None:
    _preflight()
    _create_table()
    _create_append_function()
    _create_read_policies()
    _grant_permissions()


def _preflight() -> None:
    op.execute(
        """
        DO $checks$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_roles
                WHERE rolname = 'prospect_app' AND rolcanlogin AND NOT rolsuper
                  AND NOT rolbypassrls AND NOT rolcreaterole AND NOT rolcreatedb AND NOT rolinherit
            ) THEN
                RAISE EXCEPTION 'Le rôle prospect_app est absent ou possède des attributs interdits.';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_roles
                WHERE rolname = 'prospect_rls_definer' AND NOT rolcanlogin
                  AND NOT rolsuper AND rolbypassrls
            ) THEN
                RAISE EXCEPTION 'Le rôle prospect_rls_definer est absent ou incorrect.';
            END IF;
        END
        $checks$;
        """
    )


def _create_table() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=96), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("schema_version", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("scope IN ('tenant', 'platform')", name=op.f("ck_audit_events_scope_allowed")),
        sa.CheckConstraint(
            "scope <> 'tenant' OR organization_id IS NOT NULL",
            name=op.f("ck_audit_events_tenant_has_organization"),
        ),
        sa.CheckConstraint(
            "actor_kind IN ('user', 'system')",
            name=op.f("ck_audit_events_actor_kind_allowed"),
        ),
        sa.CheckConstraint(
            "actor_kind <> 'user' OR actor_id IS NOT NULL",
            name=op.f("ck_audit_events_user_has_actor"),
        ),
        sa.CheckConstraint(
            "actor_kind <> 'system' OR actor_id IS NULL",
            name=op.f("ck_audit_events_system_has_no_actor"),
        ),
        sa.CheckConstraint(
            "action ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'",
            name=op.f("ck_audit_events_action_format"),
        ),
        sa.CheckConstraint(
            "entity_type ~ '^[a-z][a-z0-9_]{0,63}$'",
            name=op.f("ck_audit_events_entity_type_format"),
        ),
        sa.CheckConstraint(
            "char_length(request_id) BETWEEN 1 AND 128 AND request_id !~ '[[:cntrl:]]'",
            name=op.f("ck_audit_events_request_id_format"),
        ),
        sa.CheckConstraint(
            "char_length(correlation_id) BETWEEN 1 AND 128 AND correlation_id !~ '[[:cntrl:]]'",
            name=op.f("ck_audit_events_correlation_id_format"),
        ),
        sa.CheckConstraint(
            "source IN ('api', 'cli', 'worker')",
            name=op.f("ck_audit_events_source_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata) = 'object' AND octet_length(metadata::text) <= 8192",
            name=op.f("ck_audit_events_metadata_object_size"),
        ),
        sa.CheckConstraint(
            "schema_version > 0",
            name=op.f("ck_audit_events_schema_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_audit_events_actor_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_audit_events_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.execute(
        "CREATE INDEX ix_audit_events_scope_organization_occurred_id "
        "ON public.audit_events (scope, organization_id, occurred_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX ix_audit_events_scope_organization_entity_occurred_id "
        "ON public.audit_events (scope, organization_id, entity_type, entity_id, occurred_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX ix_audit_events_scope_actor_occurred_id "
        "ON public.audit_events (scope, actor_id, occurred_at DESC, id DESC)"
    )
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    op.execute(
        "CREATE INDEX ix_audit_events_platform_occurred_id "
        "ON public.audit_events (occurred_at DESC, id DESC) WHERE scope = 'platform'"
    )


def _create_append_function() -> None:
    op.execute(
        """
        CREATE FUNCTION app_private.append_audit_event(
            p_id uuid,
            p_scope text,
            p_organization_id uuid,
            p_actor_kind text,
            p_actor_id uuid,
            p_action text,
            p_entity_type text,
            p_entity_id uuid,
            p_request_id text,
            p_correlation_id text,
            p_source text,
            p_metadata jsonb,
            p_schema_version smallint
        )
        RETURNS uuid
        LANGUAGE plpgsql
        VOLATILE
        SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $function$
        DECLARE
            v_context_actor uuid;
            v_context_organization uuid;
            v_context_request text;
        BEGIN
            v_context_actor := app_private.current_actor_id();
            v_context_organization := app_private.current_organization_id();
            v_context_request := pg_catalog.current_setting('app.request_id', true);

            IF p_id IS NULL OR p_request_id IS NULL OR v_context_request IS DISTINCT FROM p_request_id THEN
                RAISE EXCEPTION 'Contexte de requête d audit invalide.' USING ERRCODE = '22023';
            END IF;
            IF p_actor_kind = 'user' THEN
                IF p_actor_id IS NULL OR v_context_actor IS DISTINCT FROM p_actor_id THEN
                    RAISE EXCEPTION 'Contexte acteur d audit invalide.' USING ERRCODE = '22023';
                END IF;
            ELSIF p_actor_kind = 'system' THEN
                IF p_actor_id IS NOT NULL OR v_context_actor IS NOT NULL OR p_source = 'api' THEN
                    RAISE EXCEPTION 'Contexte système d audit invalide.' USING ERRCODE = '22023';
                END IF;
            ELSE
                RAISE EXCEPTION 'Type d acteur d audit invalide.' USING ERRCODE = '22023';
            END IF;

            IF p_scope = 'tenant' THEN
                IF p_organization_id IS NULL
                   OR v_context_organization IS DISTINCT FROM p_organization_id THEN
                    RAISE EXCEPTION 'Contexte locataire d audit invalide.' USING ERRCODE = '22023';
                END IF;
                IF p_actor_kind = 'user' AND NOT EXISTS (
                    SELECT 1
                    FROM public.users AS actor
                    JOIN public.memberships AS membership ON membership.user_id = actor.id
                    JOIN public.organizations AS organization ON organization.id = membership.organization_id
                    WHERE actor.id = p_actor_id AND actor.status = 'active'
                      AND membership.organization_id = p_organization_id
                      AND membership.status = 'active' AND organization.status = 'active'
                ) THEN
                    RAISE EXCEPTION 'Acteur locataire d audit non autorisé.' USING ERRCODE = '42501';
                END IF;
                IF p_actor_kind = 'system' AND NOT EXISTS (
                    SELECT 1 FROM public.organizations
                    WHERE id = p_organization_id AND status = 'active'
                ) THEN
                    RAISE EXCEPTION 'Organisation d audit inactive.' USING ERRCODE = '42501';
                END IF;
            ELSIF p_scope = 'platform' THEN
                IF v_context_organization IS NOT NULL THEN
                    RAISE EXCEPTION 'Une écriture plateforme ne porte pas de contexte locataire.' USING ERRCODE = '22023';
                END IF;
                IF p_actor_kind = 'user' AND NOT EXISTS (
                    SELECT 1 FROM public.users
                    WHERE id = p_actor_id AND status = 'active' AND platform_role = 'platform_admin'
                ) THEN
                    RAISE EXCEPTION 'Acteur plateforme d audit non autorisé.' USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'Portée d audit invalide.' USING ERRCODE = '22023';
            END IF;

            INSERT INTO public.audit_events (
                id, scope, organization_id, actor_kind, actor_id, action, entity_type,
                entity_id, request_id, correlation_id, source, metadata, schema_version,
                occurred_at
            ) VALUES (
                p_id, p_scope, p_organization_id, p_actor_kind, p_actor_id, p_action,
                p_entity_type, p_entity_id, p_request_id, p_correlation_id, p_source,
                p_metadata, p_schema_version, pg_catalog.clock_timestamp()
            );
            RETURN p_id;
        END
        $function$
        """
    )
    op.execute(f"ALTER FUNCTION {_APPEND_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_APPEND_SIGNATURE} FROM PUBLIC")


def _create_read_policies() -> None:
    op.execute("ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.audit_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_events_tenant_read
        ON public.audit_events
        FOR SELECT
        TO prospect_app
        USING (
            scope = 'tenant'
            AND organization_id = app_private.current_organization_id()
            AND pg_catalog.current_setting('app.audit_scope', true) = 'tenant'
            AND EXISTS (
                SELECT 1
                FROM public.users AS reader
                JOIN public.memberships AS membership ON membership.user_id = reader.id
                JOIN public.organizations AS organization ON organization.id = membership.organization_id
                WHERE reader.id = app_private.current_actor_id()
                  AND reader.status = 'active'
                  AND membership.organization_id = audit_events.organization_id
                  AND membership.status = 'active'
                  AND membership.role IN ('admin', 'manager')
                  AND organization.status = 'active'
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY audit_events_platform_read
        ON public.audit_events
        FOR SELECT
        TO prospect_app
        USING (
            scope = 'platform'
            AND pg_catalog.current_setting('app.audit_scope', true) = 'platform'
            AND EXISTS (
                SELECT 1 FROM public.users AS reader
                WHERE reader.id = app_private.current_actor_id()
                  AND reader.status = 'active'
                  AND reader.platform_role = 'platform_admin'
            )
        )
        """
    )


def _grant_permissions() -> None:
    op.execute("REVOKE ALL ON TABLE public.audit_events FROM PUBLIC")
    op.execute("REVOKE ALL ON TABLE public.audit_events FROM prospect_app")
    op.execute("GRANT SELECT ON TABLE public.audit_events TO prospect_app")
    op.execute("GRANT INSERT ON TABLE public.audit_events TO prospect_rls_definer")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_APPEND_SIGNATURE} TO prospect_app")


def downgrade() -> None:
    op.execute(
        """
        DO $checks$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.audit_events) THEN
                RAISE EXCEPTION 'Le downgrade 0006 refuse de supprimer un journal d audit non vide.';
            END IF;
        END
        $checks$;
        """
    )
    op.execute(f"DROP FUNCTION {_APPEND_SIGNATURE}")
    op.execute("DROP POLICY audit_events_platform_read ON public.audit_events")
    op.execute("DROP POLICY audit_events_tenant_read ON public.audit_events")
    op.execute("ALTER TABLE public.audit_events NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.audit_events DISABLE ROW LEVEL SECURITY")
    op.drop_table("audit_events")
