"""Creer le socle prospects de l increment 2.5.1.

Revision ID: 20260814_0009
Revises: 20260813_0008
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0009"
down_revision: str | None = "20260813_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_TABLES = (
    "source_providers",
    "acquisition_records",
    "provenance_records",
    "prospects",
    "contacts",
    "contact_channels",
    "contact_permissions",
)


def upgrade() -> None:
    _preflight()
    _create_tables()
    _create_indexes()
    _create_provenance_guard()
    _enable_rls()
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
                RAISE EXCEPTION 'Le role prospect_app est absent ou possede des attributs interdits.';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_roles
                WHERE rolname = 'prospect_rls_definer' AND NOT rolcanlogin
                  AND NOT rolsuper AND rolbypassrls
            ) THEN
                RAISE EXCEPTION 'Le role prospect_rls_definer est absent ou incorrect.';
            END IF;
        END
        $checks$;
        """
    )


def _create_tables() -> None:
    op.create_table(
        "source_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "source_kind IN ('csv', 'facebook', 'linkedin', 'open_data', 'api', 'other')",
            name=op.f("ck_source_providers_source_kind_allowed"),
        ),
        sa.CheckConstraint("char_length(label) BETWEEN 1 AND 160", name=op.f("ck_source_providers_label_length")),
        sa.CheckConstraint("status IN ('active', 'disabled')", name=op.f("ck_source_providers_status_allowed")),
        sa.CheckConstraint("version > 0", name=op.f("ck_source_providers_version_positive")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_source_providers_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_providers")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_source_providers_organization_id_id")),
    )

    op.create_table(
        "acquisition_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_label", sa.String(length=160), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("territory", sa.String(length=120), nullable=True),
        sa.Column("obtained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("declared_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'declared'"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "source_kind IN ('google_maps', 'csv', 'facebook', 'linkedin', 'open_data', 'api', 'manual', 'other')",
            name=op.f("ck_acquisition_records_source_kind_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(source_label) BETWEEN 1 AND 160",
            name=op.f("ck_acquisition_records_source_label_length"),
        ),
        sa.CheckConstraint("char_length(purpose) BETWEEN 1 AND 64", name=op.f("ck_acquisition_records_purpose_length")),
        sa.CheckConstraint(
            "territory IS NULL OR char_length(territory) BETWEEN 1 AND 120",
            name=op.f("ck_acquisition_records_territory_length"),
        ),
        sa.CheckConstraint(
            "status IN ('declared', 'reviewed', 'rejected')",
            name=op.f("ck_acquisition_records_status_allowed"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_acquisition_records_version_positive")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_acquisition_records_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["declared_by"],
            ["users.id"],
            name=op.f("fk_acquisition_records_declared_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "provider_id"],
            ["source_providers.organization_id", "source_providers.id"],
            name=op.f("fk_acquisition_records_organization_id_provider_id_source_providers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_acquisition_records")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_acquisition_records_organization_id_id")),
    )

    op.create_table(
        "provenance_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_label", sa.String(length=160), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_ref", sa.String(length=256), nullable=True),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("territory", sa.String(length=120), nullable=True),
        sa.Column("obtained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "source_kind IN ('google_maps', 'manual', 'csv', 'facebook', 'linkedin', 'open_data', 'api', 'other')",
            name=op.f("ck_provenance_records_source_kind_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(source_label) BETWEEN 1 AND 160",
            name=op.f("ck_provenance_records_source_label_length"),
        ),
        sa.CheckConstraint(
            "evidence_ref IS NULL OR char_length(evidence_ref) BETWEEN 1 AND 256",
            name=op.f("ck_provenance_records_evidence_ref_length"),
        ),
        sa.CheckConstraint("char_length(purpose) BETWEEN 1 AND 64", name=op.f("ck_provenance_records_purpose_length")),
        sa.CheckConstraint(
            "territory IS NULL OR char_length(territory) BETWEEN 1 AND 120",
            name=op.f("ck_provenance_records_territory_length"),
        ),
        sa.CheckConstraint(
            "verified_at IS NULL OR verified_at >= obtained_at",
            name=op.f("ck_provenance_records_verification_after_obtained"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_provenance_records_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attested_by"],
            ["users.id"],
            name=op.f("fk_provenance_records_attested_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "provider_id"],
            ["source_providers.organization_id", "source_providers.id"],
            name=op.f("fk_provenance_records_organization_id_provider_id_source_providers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provenance_records")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_provenance_records_organization_id_id")),
    )

    op.create_table(
        "prospects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("google_place_id", sa.String(length=255), nullable=True),
        sa.Column("internal_alias", sa.String(length=160), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("source_label", sa.String(length=160), nullable=False),
        sa.Column("acquisition_record_id", sa.Uuid(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("stage_code", sa.String(length=32), server_default=sa.text("'new'"), nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("retention_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "google_place_id IS NULL OR char_length(google_place_id) BETWEEN 1 AND 255",
            name=op.f("ck_prospects_google_place_id_length"),
        ),
        sa.CheckConstraint(
            "char_length(internal_alias) BETWEEN 1 AND 160",
            name=op.f("ck_prospects_internal_alias_length"),
        ),
        sa.CheckConstraint(
            "origin IN ('google_place', 'manual', 'import', 'connector', 'open_data')",
            name=op.f("ck_prospects_origin_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(source_label) BETWEEN 1 AND 160",
            name=op.f("ck_prospects_source_label_length"),
        ),
        sa.CheckConstraint(
            "stage_code IN ('new', 'qualified', 'contacted', 'proposal_sent', 'won', 'lost', 'archived')",
            name=op.f("ck_prospects_stage_code_allowed"),
        ),
        sa.CheckConstraint("priority BETWEEN 0 AND 5", name=op.f("ck_prospects_priority_range")),
        sa.CheckConstraint("version > 0", name=op.f("ck_prospects_version_positive")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_prospects_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "acquisition_record_id"],
            ["acquisition_records.organization_id", "acquisition_records.id"],
            name=op.f("fk_prospects_organization_id_acquisition_record_id_acquisition_records"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "owner_id"],
            ["memberships.organization_id", "memberships.id"],
            name=op.f("fk_prospects_organization_id_owner_id_memberships"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prospects")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_prospects_organization_id_id")),
    )

    op.create_table(
        "contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("prospect_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("role_label", sa.String(length=120), nullable=True),
        sa.Column("provenance_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("char_length(display_name) BETWEEN 1 AND 160", name=op.f("ck_contacts_display_name_length")),
        sa.CheckConstraint(
            "role_label IS NULL OR char_length(role_label) BETWEEN 1 AND 120",
            name=op.f("ck_contacts_role_label_length"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_contacts_version_positive")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_contacts_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "prospect_id"],
            ["prospects.organization_id", "prospects.id"],
            name=op.f("fk_contacts_organization_id_prospect_id_prospects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "provenance_id"],
            ["provenance_records.organization_id", "provenance_records.id"],
            name=op.f("fk_contacts_organization_id_provenance_id_provenance_records"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_contacts_organization_id_id")),
    )

    op.create_table(
        "contact_channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("prospect_id", sa.Uuid(), nullable=True),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("channel_type", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_normalized", sa.String(length=512), nullable=False),
        sa.Column("provenance_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("obtained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(prospect_id IS NULL) <> (contact_id IS NULL)", name=op.f("ck_contact_channels_target_xor")
        ),
        sa.CheckConstraint(
            "channel_type IN ('email', 'phone', 'linkedin', 'facebook', 'other')",
            name=op.f("ck_contact_channels_channel_type_allowed"),
        ),
        sa.CheckConstraint("char_length(value) BETWEEN 1 AND 512", name=op.f("ck_contact_channels_value_length")),
        sa.CheckConstraint(
            "char_length(value_normalized) BETWEEN 1 AND 512",
            name=op.f("ck_contact_channels_value_normalized_length"),
        ),
        sa.CheckConstraint("char_length(purpose) BETWEEN 1 AND 64", name=op.f("ck_contact_channels_purpose_length")),
        sa.CheckConstraint(
            "verified_at IS NULL OR obtained_at IS NULL OR verified_at >= obtained_at",
            name=op.f("ck_contact_channels_verification_after_obtained"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_contact_channels_version_positive")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_contact_channels_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "prospect_id"],
            ["prospects.organization_id", "prospects.id"],
            name=op.f("fk_contact_channels_organization_id_prospect_id_prospects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "contact_id"],
            ["contacts.organization_id", "contacts.id"],
            name=op.f("fk_contact_channels_organization_id_contact_id_contacts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "provenance_id"],
            ["provenance_records.organization_id", "provenance_records.id"],
            name=op.f("fk_contact_channels_organization_id_provenance_id_provenance_records"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_contact_channels_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_channels")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_contact_channels_organization_id_id")),
    )

    op.create_table(
        "contact_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("provenance_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=160), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "status IN ('unknown', 'allowed', 'do_not_contact', 'opted_out')",
            name=op.f("ck_contact_permissions_status_allowed"),
        ),
        sa.CheckConstraint(
            "reason IS NULL OR char_length(reason) BETWEEN 1 AND 160",
            name=op.f("ck_contact_permissions_reason_length"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_contact_permissions_version_positive")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_contact_permissions_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "channel_id"],
            ["contact_channels.organization_id", "contact_channels.id"],
            name=op.f("fk_contact_permissions_organization_id_channel_id_contact_channels"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "provenance_id"],
            ["provenance_records.organization_id", "provenance_records.id"],
            name=op.f("fk_contact_permissions_organization_id_provenance_id_provenance_records"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_permissions")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_contact_permissions_organization_id_id")),
    )


def _create_indexes() -> None:
    op.create_index(
        "ix_source_providers_organization_source_kind", "source_providers", ["organization_id", "source_kind"]
    )
    op.create_index(
        "ix_acquisition_records_organization_source_obtained",
        "acquisition_records",
        ["organization_id", "source_kind", "obtained_at"],
    )
    op.create_index(
        "ix_provenance_records_organization_source_obtained",
        "provenance_records",
        ["organization_id", "source_kind", "obtained_at"],
    )
    op.create_index("ix_prospects_organization_stage", "prospects", ["organization_id", "stage_code"])
    op.create_index("ix_prospects_organization_owner", "prospects", ["organization_id", "owner_id"])
    op.create_index(
        "ix_prospects_organization_retention_review",
        "prospects",
        ["organization_id", "retention_review_at"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_prospects_active_google_place "
        "ON public.prospects (organization_id, google_place_id) "
        "WHERE google_place_id IS NOT NULL AND archived_at IS NULL"
    )
    op.create_index("ix_contacts_organization_prospect", "contacts", ["organization_id", "prospect_id"])
    op.create_index(
        "ix_contact_channels_organization_type_normalized",
        "contact_channels",
        ["organization_id", "channel_type", "value_normalized"],
    )
    op.create_index("ix_contact_channels_organization_prospect", "contact_channels", ["organization_id", "prospect_id"])
    op.create_index("ix_contact_channels_organization_contact", "contact_channels", ["organization_id", "contact_id"])
    op.create_index("ix_contact_permissions_organization_status", "contact_permissions", ["organization_id", "status"])


def _create_provenance_guard() -> None:
    op.execute(
        """
        CREATE FUNCTION app_private.reject_google_maps_contact_channel_provenance()
        RETURNS trigger
        LANGUAGE plpgsql
        VOLATILE
        SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $function$
        DECLARE
            v_source_kind text;
        BEGIN
            SELECT source_kind INTO v_source_kind
            FROM public.provenance_records
            WHERE organization_id = NEW.organization_id AND id = NEW.provenance_id;

            IF v_source_kind = 'google_maps' THEN
                RAISE EXCEPTION 'google_maps is not allowed as persistent contact channel provenance'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END
        $function$;
        """
    )
    op.execute(
        "ALTER FUNCTION app_private.reject_google_maps_contact_channel_provenance() OWNER TO prospect_rls_definer"
    )
    op.execute("REVOKE ALL ON FUNCTION app_private.reject_google_maps_contact_channel_provenance() FROM PUBLIC")
    op.execute(
        """
        CREATE TRIGGER contact_channels_reject_google_maps_provenance
        BEFORE INSERT OR UPDATE OF provenance_id, organization_id
        ON public.contact_channels
        FOR EACH ROW
        EXECUTE FUNCTION app_private.reject_google_maps_contact_channel_provenance()
        """
    )


def _enable_rls() -> None:
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


def _grant_permissions() -> None:
    tables = ", ".join(f"public.{table_name}" for table_name in _TENANT_TABLES)
    op.execute(f"REVOKE ALL ON TABLE {tables} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON TABLE {tables} FROM prospect_app")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {tables} TO prospect_app")
    op.execute("GRANT SELECT ON TABLE public.provenance_records TO prospect_rls_definer")


def downgrade() -> None:
    op.execute(
        """
        DO $checks$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM (
                    SELECT count(*) AS row_count FROM public.source_providers
                    UNION ALL SELECT count(*) FROM public.acquisition_records
                    UNION ALL SELECT count(*) FROM public.provenance_records
                    UNION ALL SELECT count(*) FROM public.prospects
                    UNION ALL SELECT count(*) FROM public.contacts
                    UNION ALL SELECT count(*) FROM public.contact_channels
                    UNION ALL SELECT count(*) FROM public.contact_permissions
                ) AS forbidden
                WHERE row_count > 0
            ) THEN
                RAISE EXCEPTION 'Le downgrade 0009 refuse de supprimer des tables prospects non vides.';
            END IF;
        END
        $checks$;
        """
    )
    op.execute("DROP TRIGGER contact_channels_reject_google_maps_provenance ON public.contact_channels")
    op.execute("DROP FUNCTION app_private.reject_google_maps_contact_channel_provenance()")
    for table_name in reversed(_TENANT_TABLES):
        op.execute(f"DROP POLICY {table_name}_tenant_isolation ON public.{table_name}")
        op.execute(f"ALTER TABLE public.{table_name} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table_name} DISABLE ROW LEVEL SECURITY")
    for table_name in reversed(_TENANT_TABLES):
        op.drop_table(table_name)
