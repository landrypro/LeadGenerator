"""Ajouter provenance, permissions et fournisseurs 2.5.3.

Revision ID: 20260814_0010
Revises: 20260814_0009
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0010"
down_revision: str | None = "20260814_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _source_providers()
    _acquisition_records()
    _provenance_records()
    _contact_permissions()
    _permission_trigger()


def _source_providers() -> None:
    op.add_column("source_providers", sa.Column("terms_reference", sa.String(length=256), nullable=True))
    op.add_column("source_providers", sa.Column("terms_url", sa.String(length=256), nullable=True))
    op.add_column("source_providers", sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True))
    op.add_column("source_providers", sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "source_providers",
        sa.Column(
            "allowed_territories",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "source_providers",
        sa.Column(
            "allowed_purposes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "source_providers",
        sa.Column(
            "allowed_data_categories",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("source_providers", sa.Column("rights_attested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("source_providers", sa.Column("rights_attested_by", sa.Uuid(), nullable=True))
    op.execute("UPDATE public.source_providers SET status = 'suspended' WHERE status = 'disabled'")
    op.alter_column("source_providers", "status", server_default=sa.text("'draft'"))
    op.drop_constraint(op.f("ck_source_providers_status_allowed"), "source_providers", type_="check")
    op.create_check_constraint(
        op.f("ck_source_providers_status_allowed"),
        "source_providers",
        "status IN ('draft', 'active', 'suspended', 'retired')",
    )
    op.create_check_constraint(
        op.f("ck_source_providers_allowed_territories_array"),
        "source_providers",
        "allowed_territories IS NOT NULL AND jsonb_typeof(allowed_territories) = 'array'",
    )
    op.create_check_constraint(
        op.f("ck_source_providers_allowed_purposes_array"),
        "source_providers",
        "allowed_purposes IS NOT NULL AND jsonb_typeof(allowed_purposes) = 'array'",
    )
    op.create_check_constraint(
        op.f("ck_source_providers_allowed_data_categories_array"),
        "source_providers",
        "allowed_data_categories IS NOT NULL AND jsonb_typeof(allowed_data_categories) = 'array'",
    )
    op.create_foreign_key(
        op.f("fk_source_providers_rights_attested_by_users"),
        "source_providers",
        "users",
        ["rights_attested_by"],
        ["id"],
        ondelete="RESTRICT",
    )


def _acquisition_records() -> None:
    op.add_column("acquisition_records", sa.Column("external_reference", sa.String(length=128), nullable=True))
    op.add_column(
        "acquisition_records",
        sa.Column(
            "data_categories",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("acquisition_records", sa.Column("decision_reason_code", sa.String(length=64), nullable=True))
    op.add_column("acquisition_records", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("acquisition_records", sa.Column("decided_by", sa.Uuid(), nullable=True))
    op.add_column("acquisition_records", sa.Column("declaration_idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("acquisition_records", sa.Column("declaration_fingerprint", sa.String(length=128), nullable=True))
    op.execute(
        """
        UPDATE public.acquisition_records
        SET status = CASE status
            WHEN 'declared' THEN 'pending_review'
            WHEN 'reviewed' THEN 'approved'
            ELSE status
        END
        """
    )
    op.alter_column("acquisition_records", "status", server_default=sa.text("'pending_review'"))
    op.drop_constraint(op.f("ck_acquisition_records_status_allowed"), "acquisition_records", type_="check")
    op.create_check_constraint(
        op.f("ck_acquisition_records_status_allowed"),
        "acquisition_records",
        "status IN ('pending_review', 'approved', 'quarantined', 'rejected')",
    )
    op.create_check_constraint(
        op.f("ck_acquisition_records_data_categories_array"),
        "acquisition_records",
        "data_categories IS NOT NULL AND jsonb_typeof(data_categories) = 'array'",
    )
    op.create_foreign_key(
        op.f("fk_acquisition_records_decided_by_users"),
        "acquisition_records",
        "users",
        ["decided_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_acquisition_records_declaration_idempotency",
        "acquisition_records",
        ["organization_id", "declaration_idempotency_key"],
        unique=True,
        postgresql_where=sa.text("declaration_idempotency_key IS NOT NULL"),
    )


def _provenance_records() -> None:
    op.add_column("provenance_records", sa.Column("acquisition_record_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_provenance_records_organization_id_acquisition_record_id_acquisition_records"),
        "provenance_records",
        "acquisition_records",
        ["organization_id", "acquisition_record_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )


def _contact_permissions() -> None:
    op.add_column("contact_permissions", sa.Column("legal_basis_code", sa.String(length=64), nullable=True))
    op.add_column("contact_permissions", sa.Column("decided_by", sa.Uuid(), nullable=True))
    op.add_column("contact_permissions", sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contact_permissions", sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f("ck_contact_permissions_legal_basis_code_allowed"),
        "contact_permissions",
        "legal_basis_code IS NULL OR legal_basis_code IN "
        "('consent', 'contract', 'legitimate_interest', 'customer_request', 'other')",
    )
    op.create_check_constraint(
        op.f("ck_contact_permissions_validity_order"),
        "contact_permissions",
        "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
    )
    op.create_foreign_key(
        op.f("fk_contact_permissions_decided_by_users"),
        "contact_permissions",
        "users",
        ["decided_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        op.f("uq_contact_permissions_organization_id_channel_id"),
        "contact_permissions",
        ["organization_id", "channel_id"],
    )


def _permission_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION app_private.ensure_unknown_contact_permission()
        RETURNS trigger
        LANGUAGE plpgsql
        VOLATILE
        SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $function$
        BEGIN
            INSERT INTO public.contact_permissions (id, organization_id, channel_id, status, created_at, updated_at)
            VALUES (gen_random_uuid(), NEW.organization_id, NEW.id, 'unknown', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (organization_id, channel_id) DO NOTHING;
            RETURN NEW;
        END
        $function$;
        """
    )
    op.execute("ALTER FUNCTION app_private.ensure_unknown_contact_permission() OWNER TO prospect_rls_definer")
    op.execute("REVOKE ALL ON FUNCTION app_private.ensure_unknown_contact_permission() FROM PUBLIC")
    op.execute("GRANT INSERT ON TABLE public.contact_permissions TO prospect_rls_definer")
    op.execute(
        """
        CREATE TRIGGER contact_channels_ensure_unknown_permission
        AFTER INSERT ON public.contact_channels
        FOR EACH ROW
        EXECUTE FUNCTION app_private.ensure_unknown_contact_permission()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $checks$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.source_providers
                WHERE terms_reference IS NOT NULL
                   OR terms_url IS NOT NULL
                   OR valid_from IS NOT NULL
                   OR valid_until IS NOT NULL
                   OR rights_attested_at IS NOT NULL
                   OR rights_attested_by IS NOT NULL
                   OR allowed_territories <> '[]'::jsonb
                   OR allowed_purposes <> '[]'::jsonb
                   OR allowed_data_categories <> '[]'::jsonb
            ) THEN
                RAISE EXCEPTION 'Le downgrade 0010 refuse de perdre les donnees fournisseur 2.5.3.';
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.acquisition_records
                WHERE external_reference IS NOT NULL
                   OR decision_reason_code IS NOT NULL
                   OR decided_at IS NOT NULL
                   OR decided_by IS NOT NULL
                   OR declaration_idempotency_key IS NOT NULL
                   OR declaration_fingerprint IS NOT NULL
                   OR data_categories <> '[]'::jsonb
            ) THEN
                RAISE EXCEPTION 'Le downgrade 0010 refuse de perdre les donnees acquisition 2.5.3.';
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.provenance_records WHERE acquisition_record_id IS NOT NULL
            ) THEN
                RAISE EXCEPTION 'Le downgrade 0010 refuse de perdre les liens provenance/acquisition.';
            END IF;
        END
        $checks$;
        """
    )
    op.execute("DROP TRIGGER contact_channels_ensure_unknown_permission ON public.contact_channels")
    op.execute("DROP FUNCTION app_private.ensure_unknown_contact_permission()")
    op.execute("REVOKE INSERT ON TABLE public.contact_permissions FROM prospect_rls_definer")
    op.drop_constraint(op.f("uq_contact_permissions_organization_id_channel_id"), "contact_permissions", type_="unique")
    op.drop_constraint(op.f("fk_contact_permissions_decided_by_users"), "contact_permissions", type_="foreignkey")
    op.drop_constraint(op.f("ck_contact_permissions_validity_order"), "contact_permissions", type_="check")
    op.drop_constraint(op.f("ck_contact_permissions_legal_basis_code_allowed"), "contact_permissions", type_="check")
    op.drop_column("contact_permissions", "valid_until")
    op.drop_column("contact_permissions", "valid_from")
    op.drop_column("contact_permissions", "decided_by")
    op.drop_column("contact_permissions", "legal_basis_code")
    op.drop_constraint(
        op.f("fk_provenance_records_organization_id_acquisition_record_id_acquisition_records"),
        "provenance_records",
        type_="foreignkey",
    )
    op.drop_column("provenance_records", "acquisition_record_id")
    op.drop_index("uq_acquisition_records_declaration_idempotency", table_name="acquisition_records")
    op.drop_constraint(op.f("fk_acquisition_records_decided_by_users"), "acquisition_records", type_="foreignkey")
    op.drop_constraint(op.f("ck_acquisition_records_data_categories_array"), "acquisition_records", type_="check")
    op.drop_constraint(op.f("ck_acquisition_records_status_allowed"), "acquisition_records", type_="check")
    op.execute(
        """
        UPDATE public.acquisition_records
        SET status = CASE status
            WHEN 'pending_review' THEN 'declared'
            WHEN 'approved' THEN 'reviewed'
            ELSE 'rejected'
        END
        """
    )
    op.alter_column("acquisition_records", "status", server_default=sa.text("'declared'"))
    op.create_check_constraint(
        op.f("ck_acquisition_records_status_allowed"),
        "acquisition_records",
        "status IN ('declared', 'reviewed', 'rejected')",
    )
    op.drop_column("acquisition_records", "declaration_fingerprint")
    op.drop_column("acquisition_records", "declaration_idempotency_key")
    op.drop_column("acquisition_records", "decided_by")
    op.drop_column("acquisition_records", "decided_at")
    op.drop_column("acquisition_records", "decision_reason_code")
    op.drop_column("acquisition_records", "data_categories")
    op.drop_column("acquisition_records", "external_reference")
    op.drop_constraint(op.f("fk_source_providers_rights_attested_by_users"), "source_providers", type_="foreignkey")
    op.drop_constraint(op.f("ck_source_providers_allowed_data_categories_array"), "source_providers", type_="check")
    op.drop_constraint(op.f("ck_source_providers_allowed_purposes_array"), "source_providers", type_="check")
    op.drop_constraint(op.f("ck_source_providers_allowed_territories_array"), "source_providers", type_="check")
    op.drop_constraint(op.f("ck_source_providers_status_allowed"), "source_providers", type_="check")
    op.execute(
        "UPDATE public.source_providers SET status = 'disabled' WHERE status IN ('draft', 'suspended', 'retired')"
    )
    op.alter_column("source_providers", "status", server_default=sa.text("'active'"))
    op.create_check_constraint(
        op.f("ck_source_providers_status_allowed"),
        "source_providers",
        "status IN ('active', 'disabled')",
    )
    op.drop_column("source_providers", "rights_attested_by")
    op.drop_column("source_providers", "rights_attested_at")
    op.drop_column("source_providers", "allowed_data_categories")
    op.drop_column("source_providers", "allowed_purposes")
    op.drop_column("source_providers", "allowed_territories")
    op.drop_column("source_providers", "valid_until")
    op.drop_column("source_providers", "valid_from")
    op.drop_column("source_providers", "terms_url")
    op.drop_column("source_providers", "terms_reference")
