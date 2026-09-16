"""Ajouter conservation et declarations d import 2.5.4.

Revision ID: 20260814_0011
Revises: 20260814_0010
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0011"
down_revision: str | None = "20260814_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_TABLES = ("retention_policies", "retention_holds", "import_declarations")


def upgrade() -> None:
    _archive_metadata()
    _retention_policies()
    _retention_holds()
    _import_declarations()
    _hold_target_trigger()
    _enable_rls_and_grants()


def _archive_metadata() -> None:
    for table_name in ("prospects", "contacts", "contact_channels"):
        op.add_column(table_name, sa.Column("archived_by", sa.Uuid(), nullable=True))
        op.add_column(table_name, sa.Column("archive_reason_code", sa.String(length=64), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table_name}_archived_by_users"),
            table_name,
            "users",
            ["archived_by"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_check_constraint(
            op.f(f"ck_{table_name}_archive_reason_code_allowed"),
            table_name,
            "archive_reason_code IS NULL OR archive_reason_code IN "
            "('duplicate', 'invalid_data', 'no_longer_relevant', 'relationship_ended', 'import_cancelled', 'other')",
        )


def _retention_policies() -> None:
    op.create_table(
        "retention_policies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("policy_code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("review_after_days", sa.Integer(), nullable=False),
        sa.Column("archive_after_days", sa.Integer(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint(
            "resource_type IN ('prospect', 'contact', 'contact_channel', 'acquisition_record', "
            "'provenance_record', 'import_declaration')",
            name=op.f("ck_retention_policies_resource_type_allowed"),
        ),
        sa.CheckConstraint("char_length(policy_code) BETWEEN 1 AND 64", name=op.f("ck_retention_policies_code_length")),
        sa.CheckConstraint("char_length(label) BETWEEN 1 AND 160", name=op.f("ck_retention_policies_label_length")),
        sa.CheckConstraint("status IN ('draft', 'active', 'superseded')", name=op.f("ck_retention_policies_status")),
        sa.CheckConstraint("review_after_days BETWEEN 1 AND 36500", name=op.f("ck_retention_policies_review_days")),
        sa.CheckConstraint(
            "archive_after_days IS NULL OR archive_after_days BETWEEN review_after_days AND 36500",
            name=op.f("ck_retention_policies_archive_days"),
        ),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name=op.f("ck_retention_policies_effective_order"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_retention_policies_version_positive")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_retention_policies_organization_id_id")),
    )
    op.create_index(
        "ix_retention_policies_organization_resource_status",
        "retention_policies",
        ["organization_id", "resource_type", "status"],
    )
    op.create_index(
        "uq_retention_policies_one_active",
        "retention_policies",
        ["organization_id", "resource_type"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def _retention_holds() -> None:
    op.create_table(
        "retention_holds",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("placed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("release_reason_code", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("command_fingerprint", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint(
            "resource_type IN ('prospect', 'contact', 'contact_channel', 'acquisition_record', "
            "'provenance_record', 'import_declaration')",
            name=op.f("ck_retention_holds_resource_type_allowed"),
        ),
        sa.CheckConstraint(
            "reason_code IN ('legal_request', 'contractual_obligation', 'investigation', "
            "'data_subject_request', 'quality_review', 'other')",
            name=op.f("ck_retention_holds_reason_code_allowed"),
        ),
        sa.CheckConstraint(
            "release_reason_code IS NULL OR release_reason_code IN ('resolved', 'expired', 'entered_in_error', 'other')",
            name=op.f("ck_retention_holds_release_reason_code_allowed"),
        ),
        sa.CheckConstraint("reason_code <> 'other' OR note IS NOT NULL", name=op.f("ck_retention_holds_other_note")),
        sa.CheckConstraint(
            "released_at IS NULL OR released_at >= placed_at", name=op.f("ck_retention_holds_release_order")
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_retention_holds_version_positive")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_retention_holds_organization_id_id")),
    )
    op.create_index(
        "ix_retention_holds_organization_resource",
        "retention_holds",
        ["organization_id", "resource_type", "resource_id"],
    )
    op.create_index(
        "ix_retention_holds_active",
        "retention_holds",
        ["organization_id", "resource_type", "resource_id"],
        postgresql_where=sa.text("released_at IS NULL"),
    )
    op.create_index(
        "uq_retention_holds_idempotency",
        "retention_holds",
        ["organization_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def _import_declarations() -> None:
    op.create_table(
        "import_declarations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("acquisition_record_id", sa.Uuid(), nullable=False),
        sa.Column("declaration_label", sa.String(length=160), nullable=False),
        sa.Column("format_code", sa.String(length=16), nullable=False),
        sa.Column("schema_code", sa.String(length=64), nullable=False),
        sa.Column(
            "declared_field_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "declared_data_categories",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("estimated_row_count", sa.Integer(), nullable=True),
        sa.Column("declared_content_sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "decision_reason_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("declared_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("archive_reason_code", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("command_fingerprint", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(
            ["organization_id", "acquisition_record_id"],
            ["acquisition_records.organization_id", "acquisition_records.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "char_length(declaration_label) BETWEEN 1 AND 160", name=op.f("ck_import_declarations_label")
        ),
        sa.CheckConstraint("format_code = 'csv'", name=op.f("ck_import_declarations_format_code")),
        sa.CheckConstraint("schema_code = 'prospect_contacts_v1'", name=op.f("ck_import_declarations_schema_code")),
        sa.CheckConstraint(
            "jsonb_typeof(declared_field_codes) = 'array'", name=op.f("ck_import_declarations_fields_array")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(declared_data_categories) = 'array'", name=op.f("ck_import_declarations_categories_array")
        ),
        sa.CheckConstraint(
            "estimated_row_count IS NULL OR estimated_row_count BETWEEN 1 AND 10000000",
            name=op.f("ck_import_declarations_row_count"),
        ),
        sa.CheckConstraint(
            "declared_content_sha256 IS NULL OR declared_content_sha256 ~ '^[a-f0-9]{64}$'",
            name=op.f("ck_import_declarations_sha256"),
        ),
        sa.CheckConstraint(
            "status IN ('declared', 'quarantined', 'cancelled', 'archived')",
            name=op.f("ck_import_declarations_status_allowed"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_import_declarations_version_positive")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_import_declarations_organization_id_id")),
    )
    op.create_index("ix_import_declarations_organization_status", "import_declarations", ["organization_id", "status"])
    op.create_index(
        "ix_import_declarations_organization_acquisition",
        "import_declarations",
        ["organization_id", "acquisition_record_id"],
    )
    op.create_index(
        "uq_import_declarations_idempotency",
        "import_declarations",
        ["organization_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def _hold_target_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION app_private.ensure_retention_hold_target()
        RETURNS trigger
        LANGUAGE plpgsql
        VOLATILE
        SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $function$
        BEGIN
            IF NEW.resource_type = 'prospect' AND EXISTS (
                SELECT 1 FROM public.prospects WHERE organization_id = NEW.organization_id AND id = NEW.resource_id
            ) THEN
                RETURN NEW;
            ELSIF NEW.resource_type = 'contact' AND EXISTS (
                SELECT 1 FROM public.contacts WHERE organization_id = NEW.organization_id AND id = NEW.resource_id
            ) THEN
                RETURN NEW;
            ELSIF NEW.resource_type = 'contact_channel' AND EXISTS (
                SELECT 1 FROM public.contact_channels WHERE organization_id = NEW.organization_id AND id = NEW.resource_id
            ) THEN
                RETURN NEW;
            ELSIF NEW.resource_type = 'acquisition_record' AND EXISTS (
                SELECT 1 FROM public.acquisition_records WHERE organization_id = NEW.organization_id AND id = NEW.resource_id
            ) THEN
                RETURN NEW;
            ELSIF NEW.resource_type = 'provenance_record' AND EXISTS (
                SELECT 1 FROM public.provenance_records WHERE organization_id = NEW.organization_id AND id = NEW.resource_id
            ) THEN
                RETURN NEW;
            ELSIF NEW.resource_type = 'import_declaration' AND EXISTS (
                SELECT 1 FROM public.import_declarations WHERE organization_id = NEW.organization_id AND id = NEW.resource_id
            ) THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'retention hold target is not valid for this tenant';
        END
        $function$;
        """
    )
    op.execute("ALTER FUNCTION app_private.ensure_retention_hold_target() OWNER TO prospect_rls_definer")
    op.execute("REVOKE ALL ON FUNCTION app_private.ensure_retention_hold_target() FROM PUBLIC")
    op.execute("GRANT SELECT ON TABLE public.prospects TO prospect_rls_definer")
    op.execute("GRANT SELECT ON TABLE public.contacts TO prospect_rls_definer")
    op.execute("GRANT SELECT ON TABLE public.contact_channels TO prospect_rls_definer")
    op.execute("GRANT SELECT ON TABLE public.acquisition_records TO prospect_rls_definer")
    op.execute("GRANT SELECT ON TABLE public.provenance_records TO prospect_rls_definer")
    op.execute("GRANT SELECT ON TABLE public.import_declarations TO prospect_rls_definer")
    op.execute(
        """
        CREATE TRIGGER retention_holds_validate_target
        BEFORE INSERT OR UPDATE OF resource_type, resource_id, organization_id ON public.retention_holds
        FOR EACH ROW
        EXECUTE FUNCTION app_private.ensure_retention_hold_target()
        """
    )


def _enable_rls_and_grants() -> None:
    tables = ", ".join(f"public.{table_name}" for table_name in _TENANT_TABLES)
    for table_name in _TENANT_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation
            ON public.{table_name}
            FOR ALL
            TO prospect_app
            USING (organization_id = app_private.current_organization_id())
            WITH CHECK (organization_id = app_private.current_organization_id())
            """
        )
    op.execute(f"REVOKE ALL ON TABLE {tables} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON TABLE {tables} FROM prospect_app")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {tables} TO prospect_app")


def downgrade() -> None:
    op.execute(
        """
        DO $checks$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.retention_policies)
                OR EXISTS (SELECT 1 FROM public.retention_holds)
                OR EXISTS (SELECT 1 FROM public.import_declarations)
            THEN
                RAISE EXCEPTION 'Le downgrade 0011 refuse de perdre les donnees de conservation 2.5.4.';
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.prospects
                WHERE archived_by IS NOT NULL OR archive_reason_code IS NOT NULL
            )
                OR EXISTS (
                    SELECT 1 FROM public.contacts
                    WHERE archived_by IS NOT NULL OR archive_reason_code IS NOT NULL
                )
                OR EXISTS (
                    SELECT 1 FROM public.contact_channels
                    WHERE archived_by IS NOT NULL OR archive_reason_code IS NOT NULL
                )
            THEN
                RAISE EXCEPTION 'Le downgrade 0011 refuse de perdre les metadonnees archive.';
            END IF;
        END
        $checks$;
        """
    )
    op.execute("DROP TRIGGER retention_holds_validate_target ON public.retention_holds")
    op.execute("DROP FUNCTION app_private.ensure_retention_hold_target()")
    for table_name in reversed(_TENANT_TABLES):
        op.execute(f"DROP POLICY {table_name}_tenant_isolation ON public.{table_name}")
        op.drop_table(table_name)
    for table_name in ("contact_channels", "contacts", "prospects"):
        op.drop_constraint(op.f(f"ck_{table_name}_archive_reason_code_allowed"), table_name, type_="check")
        op.drop_constraint(op.f(f"fk_{table_name}_archived_by_users"), table_name, type_="foreignkey")
        op.drop_column(table_name, "archive_reason_code")
        op.drop_column(table_name, "archived_by")
