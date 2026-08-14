"""Ajouter les operations idempotentes de statut organisation 2.4.4.

Revision ID: 20260813_0008
Revises: 20260809_0007
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0008"
down_revision: str | None = "20260809_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FUNCTION_SIGNATURE = (
    "app_private.platform_change_organization_status("
    "uuid, text, uuid, text, integer, text, text, timestamp with time zone)"
)


def upgrade() -> None:
    op.create_table(
        "organization_status_operations",
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("reason_code", sa.String(length=32), nullable=False),
        sa.Column("external_reference", sa.String(length=64), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column(
            "result_version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation IN ('suspend', 'reactivate')",
            name=op.f("ck_organization_status_operations_operation_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(fingerprint) = 64",
            name=op.f("ck_organization_status_operations_fingerprint_length"),
        ),
        sa.CheckConstraint(
            "reason_code IN ('customer_request', 'billing', 'security', 'compliance', 'administrative', 'other')",
            name=op.f("ck_organization_status_operations_reason_code_allowed"),
        ),
        sa.CheckConstraint(
            "external_reference IS NULL OR char_length(external_reference) BETWEEN 1 AND 64",
            name=op.f("ck_organization_status_operations_external_reference_length"),
        ),
        sa.CheckConstraint(
            "result_version > 0",
            name=op.f("ck_organization_status_operations_result_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_organization_status_operations_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name=op.f("fk_organization_status_operations_requested_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("operation_id", name=op.f("pk_organization_status_operations")),
    )
    op.create_index(
        "ix_organization_status_operations_organization_created",
        "organization_status_operations",
        ["organization_id", "created_at"],
    )
    op.execute("ALTER TABLE public.organization_status_operations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.organization_status_operations FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY organization_status_operations_platform_only
        ON public.organization_status_operations
        FOR ALL
        TO prospect_app
        USING (app_private.is_platform_actor())
        WITH CHECK (app_private.is_platform_actor())
        """
    )
    op.execute("REVOKE ALL ON TABLE public.organization_status_operations FROM PUBLIC")
    op.execute("REVOKE ALL ON TABLE public.organization_status_operations FROM prospect_app")
    op.execute("GRANT SELECT ON TABLE public.organization_status_operations TO prospect_app")
    op.execute("GRANT INSERT ON TABLE public.organization_status_operations TO prospect_rls_definer")
    op.execute(_CHANGE_STATUS_FUNCTION)
    op.execute(f"ALTER FUNCTION {_FUNCTION_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_FUNCTION_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_FUNCTION_SIGNATURE} TO prospect_app")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {_FUNCTION_SIGNATURE}")
    op.execute("DROP POLICY organization_status_operations_platform_only ON public.organization_status_operations")
    op.execute("ALTER TABLE public.organization_status_operations NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.organization_status_operations DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_organization_status_operations_organization_created", table_name="organization_status_operations")
    op.drop_table("organization_status_operations")


_CHANGE_STATUS_FUNCTION = r"""
CREATE FUNCTION app_private.platform_change_organization_status(
    p_organization_id uuid,
    p_operation text,
    p_operation_id uuid,
    p_fingerprint text,
    p_expected_version integer,
    p_reason_code text,
    p_external_reference text,
    p_now timestamp with time zone
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
DECLARE
    v_existing_operation public.organization_status_operations%ROWTYPE;
    v_organization public.organizations%ROWTYPE;
    v_expected_status text;
    v_target_status text;
    v_view jsonb;
BEGIN
    IF NOT app_private.is_platform_actor() THEN
        RAISE EXCEPTION 'platform capability required' USING ERRCODE = '42501';
    END IF;
    IF p_operation NOT IN ('suspend', 'reactivate') THEN
        RAISE EXCEPTION 'invalid organization status operation' USING ERRCODE = '22023';
    END IF;
    IF p_expected_version < 1 THEN
        RAISE EXCEPTION 'invalid organization version' USING ERRCODE = '22023';
    END IF;
    IF p_reason_code NOT IN ('customer_request', 'billing', 'security', 'compliance', 'administrative', 'other') THEN
        RAISE EXCEPTION 'invalid reason code' USING ERRCODE = '22023';
    END IF;
    IF p_external_reference IS NOT NULL AND (
        char_length(p_external_reference) NOT BETWEEN 1 AND 64
        OR p_external_reference !~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,63}$'
    ) THEN
        RAISE EXCEPTION 'invalid external reference' USING ERRCODE = '22023';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_operation_id::text, 0));
    SELECT * INTO v_existing_operation
    FROM public.organization_status_operations
    WHERE operation_id = p_operation_id
    FOR UPDATE;
    IF FOUND THEN
        IF v_existing_operation.fingerprint <> p_fingerprint
           OR v_existing_operation.organization_id <> p_organization_id
           OR v_existing_operation.operation <> p_operation THEN
            RETURN pg_catalog.jsonb_build_object('code', 'idempotency_conflict');
        END IF;
        SELECT pg_catalog.to_jsonb(view) INTO v_view
        FROM app_private.platform_provisioning_view(p_organization_id, p_now) AS view;
        RETURN pg_catalog.jsonb_build_object('code', 'replayed', 'view', v_view);
    END IF;

    SELECT * INTO v_organization
    FROM public.organizations
    WHERE id = p_organization_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN pg_catalog.jsonb_build_object('code', 'not_found');
    END IF;
    IF v_organization.version <> p_expected_version THEN
        RETURN pg_catalog.jsonb_build_object(
            'code', 'version_conflict',
            'current_version', v_organization.version
        );
    END IF;

    v_expected_status := CASE WHEN p_operation = 'suspend' THEN 'active' ELSE 'suspended' END;
    v_target_status := CASE WHEN p_operation = 'suspend' THEN 'suspended' ELSE 'active' END;
    IF v_organization.status <> v_expected_status THEN
        RETURN pg_catalog.jsonb_build_object(
            'code', 'invalid_transition',
            'current_version', v_organization.version
        );
    END IF;

    UPDATE public.organizations
    SET status = v_target_status,
        updated_at = p_now,
        version = version + 1
    WHERE id = p_organization_id;

    INSERT INTO public.organization_status_operations (
        operation_id, organization_id, operation, fingerprint, reason_code,
        external_reference, requested_by, result_version, created_at
    ) VALUES (
        p_operation_id, p_organization_id, p_operation, p_fingerprint, p_reason_code,
        p_external_reference, app_private.current_actor_id(), v_organization.version + 1, p_now
    );

    SELECT pg_catalog.to_jsonb(view) INTO v_view
    FROM app_private.platform_provisioning_view(p_organization_id, p_now) AS view;
    RETURN pg_catalog.jsonb_build_object('code', 'updated', 'view', v_view);
END
$function$;
"""
