"""Phase 4.3: private exports, explicit source rights and import retries.

Revision ID: 20260924_0023
Revises: 20260923_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260924_0023"
down_revision: str | None = "20260923_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EXPORT_TABLES = ("export_requests", "export_artifacts", "source_export_rules")
_WORKER_READ_TABLES = (
    "prospects",
    "contacts",
    "contact_channels",
    "contact_permissions",
    "prospect_activities",
    "prospect_tasks",
    "opportunities",
    "provenance_records",
    "acquisition_records",
    "source_providers",
)


def upgrade() -> None:
    op.create_table(
        "export_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requester_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requester_membership_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("dataset", sa.String(32), nullable=False),
        sa.Column("schema_code", sa.String(32), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("filters", JSONB(), nullable=False),
        sa.Column("columns", JSONB(), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.UniqueConstraint("organization_id", "id", name="uq_export_requests_org_id"),
        sa.UniqueConstraint("organization_id", "idempotency_digest", name="uq_export_requests_idempotency"),
        sa.UniqueConstraint("job_id", name="uq_export_requests_job"),
        sa.ForeignKeyConstraint(
            ["organization_id", "requester_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "job_id"],
            ["jobs.organization_id", "jobs.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "dataset IN ('prospects','contacts','contact_channels','activities','tasks','opportunities')",
            name="ck_export_dataset",
        ),
        sa.CheckConstraint("schema_code = 'crm_csv_v1'", name="ck_export_schema"),
        sa.CheckConstraint("scope IN ('self','organization')", name="ck_export_scope"),
        sa.CheckConstraint(
            "status IN ('queued','running','ready','failed','cancelled','expired')", name="ck_export_status"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(filters) = 'object' AND jsonb_typeof(columns) = 'array'", name="ck_export_contract"
        ),
    )
    op.create_index(
        "ix_export_requests_list", "export_requests", ["organization_id", "requester_user_id", "created_at", "id"]
    )
    op.create_index("ix_export_requests_org_status", "export_requests", ["organization_id", "status"])

    op.create_table(
        "export_artifacts",
        sa.Column("export_id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("file_ref", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("omitted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "export_id"],
            ["export_requests.organization_id", "export_requests.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("byte_size BETWEEN 1 AND 52428800", name="ck_export_artifact_size"),
        sa.CheckConstraint("row_count BETWEEN 0 AND 50000 AND omitted_count >= 0", name="ck_export_artifact_counts"),
        sa.CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name="ck_export_artifact_sha"),
        sa.CheckConstraint("expires_at > published_at", name="ck_export_artifact_expiry"),
    )
    op.create_index("ix_export_artifacts_expiry", "export_artifacts", ["expires_at", "deleted_at"])

    op.create_table(
        "source_export_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("acquisition_id", sa.Uuid(), nullable=True),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("data_category", sa.String(32), nullable=False),
        sa.Column("field_codes", JSONB(), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_ref", sa.String(256), nullable=False),
        sa.Column("attested_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("organization_id", "id", name="uq_source_export_rules_org_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "acquisition_id"],
            ["acquisition_records.organization_id", "acquisition_records.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "provider_id"],
            ["source_providers.organization_id", "source_providers.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("(acquisition_id IS NULL) <> (provider_id IS NULL)", name="ck_export_rule_target"),
        sa.CheckConstraint("status IN ('allowed','denied','unknown')", name="ck_export_rule_status"),
        sa.CheckConstraint("jsonb_typeof(field_codes) = 'array'", name="ck_export_rule_fields"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_export_rule_validity"),
        sa.CheckConstraint("version > 0", name="ck_export_rule_version"),
    )
    op.create_index(
        "ix_source_export_rules_acquisition",
        "source_export_rules",
        ["organization_id", "acquisition_id", "data_category"],
    )
    op.create_index(
        "ix_source_export_rules_provider", "source_export_rules", ["organization_id", "provider_id", "data_category"]
    )

    op.add_column("csv_import_sessions", sa.Column("retry_of_run_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_csv_import_sessions_retry_run",
        "csv_import_sessions",
        "csv_import_runs",
        ["organization_id", "retry_of_run_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_csv_import_sessions_retry_run", "csv_import_sessions", ["organization_id", "retry_of_run_id"])

    for table_name in _EXPORT_TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table_name}_tenant ON public.{table_name} FOR ALL TO prospect_app, prospect_worker
            USING (organization_id = app_private.current_organization_id())
            WITH CHECK (organization_id = app_private.current_organization_id())
        """)
        op.execute(f"REVOKE ALL ON public.{table_name} FROM PUBLIC")
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.export_requests, public.source_export_rules TO prospect_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.export_artifacts TO prospect_app")
    op.execute("GRANT SELECT, UPDATE ON public.export_requests TO prospect_worker")
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.export_artifacts TO prospect_worker")
    op.execute("GRANT SELECT ON public.source_export_rules TO prospect_worker")
    for table_name in _WORKER_READ_TABLES:
        op.execute(f"GRANT SELECT ON public.{table_name} TO prospect_worker")
        op.execute(f"""
            CREATE POLICY {table_name}_worker_export ON public.{table_name} FOR SELECT TO prospect_worker
            USING (organization_id = app_private.current_organization_id())
        """)
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_private.append_audit_event(uuid, text, uuid, text, uuid, text, text, uuid, text, text, text, jsonb, smallint) TO prospect_worker"
    )
    op.execute("GRANT SELECT ON public.export_requests, public.export_artifacts TO prospect_job_claim_owner")
    op.execute(
        "GRANT SELECT ON public.acquisition_records, public.source_providers, public.source_export_rules TO prospect_job_claim_owner"
    )
    for table_name in (
        "export_requests",
        "export_artifacts",
        "acquisition_records",
        "source_providers",
        "source_export_rules",
    ):
        op.execute(
            f"CREATE POLICY {table_name}_claim_owner ON public.{table_name} FOR SELECT TO prospect_job_claim_owner USING (true)"
        )
    op.execute("""
        CREATE FUNCTION app_private.expired_export_artifacts(p_limit integer)
        RETURNS TABLE(export_id uuid, organization_id uuid, file_ref varchar, requester_user_id uuid)
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
            SELECT a.export_id, a.organization_id, a.file_ref, r.requester_user_id
            FROM public.export_artifacts a JOIN public.export_requests r ON r.id = a.export_id
            WHERE a.deleted_at IS NULL AND (
                a.expires_at <= clock_timestamp()
                OR (r.dataset IN ('prospects','contacts','contact_channels') AND (
                EXISTS (SELECT 1 FROM public.acquisition_records acq
                    WHERE acq.organization_id = a.organization_id AND acq.updated_at > a.published_at)
                OR EXISTS (SELECT 1 FROM public.source_providers sp
                    WHERE sp.organization_id = a.organization_id AND
                        (sp.updated_at > a.published_at OR
                         (sp.valid_until > a.published_at AND sp.valid_until <= clock_timestamp())))
                OR EXISTS (SELECT 1 FROM public.source_export_rules sr
                    WHERE sr.organization_id = a.organization_id AND
                        (sr.attested_at > a.published_at OR
                         (sr.valid_until > a.published_at AND sr.valid_until <= clock_timestamp())))
                ))
            )
            ORDER BY a.expires_at, a.export_id LIMIT LEAST(GREATEST(p_limit, 1), 100)
        $$
    """)
    op.execute("ALTER FUNCTION app_private.expired_export_artifacts(integer) OWNER TO prospect_job_claim_owner")
    op.execute("REVOKE ALL ON FUNCTION app_private.expired_export_artifacts(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.expired_export_artifacts(integer) TO prospect_worker")
    op.execute("""
        CREATE FUNCTION app_private.export_artifact_exists(p_ref varchar)
        RETURNS boolean LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
            SELECT EXISTS (SELECT 1 FROM public.export_artifacts
                WHERE file_ref = p_ref AND deleted_at IS NULL)
        $$
    """)
    op.execute("ALTER FUNCTION app_private.export_artifact_exists(varchar) OWNER TO prospect_job_claim_owner")
    op.execute("REVOKE ALL ON FUNCTION app_private.export_artifact_exists(varchar) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.export_artifact_exists(varchar) TO prospect_worker")
    op.execute("""
        CREATE FUNCTION app_private.ready_export_artifacts(p_limit integer, p_after uuid)
        RETURNS TABLE(export_id uuid, organization_id uuid, file_ref varchar,
                      requester_user_id uuid, byte_size bigint)
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
            SELECT a.export_id, a.organization_id, a.file_ref, r.requester_user_id, a.byte_size
            FROM public.export_artifacts a JOIN public.export_requests r ON r.id = a.export_id
            WHERE r.status = 'ready' AND a.deleted_at IS NULL AND a.expires_at > clock_timestamp()
              AND (p_after IS NULL OR a.export_id > p_after)
            ORDER BY a.export_id LIMIT LEAST(GREATEST(p_limit, 1), 100)
        $$
    """)
    op.execute("ALTER FUNCTION app_private.ready_export_artifacts(integer, uuid) OWNER TO prospect_job_claim_owner")
    op.execute("REVOKE ALL ON FUNCTION app_private.ready_export_artifacts(integer, uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.ready_export_artifacts(integer, uuid) TO prospect_worker")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_private.ready_export_artifacts(integer, uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_private.export_artifact_exists(varchar)")
    op.execute("DROP FUNCTION IF EXISTS app_private.expired_export_artifacts(integer)")
    for table_name in (
        "export_requests",
        "export_artifacts",
        "acquisition_records",
        "source_providers",
        "source_export_rules",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table_name}_claim_owner ON public.{table_name}")
    op.execute("REVOKE SELECT ON public.export_requests, public.export_artifacts FROM prospect_job_claim_owner")
    op.execute(
        "REVOKE SELECT ON public.acquisition_records, public.source_providers, public.source_export_rules FROM prospect_job_claim_owner"
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION app_private.append_audit_event(uuid, text, uuid, text, uuid, text, text, uuid, text, text, text, jsonb, smallint) FROM prospect_worker"
    )
    for table_name in _WORKER_READ_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table_name}_worker_export ON public.{table_name}")
        op.execute(f"REVOKE SELECT ON public.{table_name} FROM prospect_worker")
    op.drop_index("ix_csv_import_sessions_retry_run", table_name="csv_import_sessions")
    op.drop_constraint("fk_csv_import_sessions_retry_run", "csv_import_sessions", type_="foreignkey")
    op.drop_column("csv_import_sessions", "retry_of_run_id")
    op.drop_table("source_export_rules")
    op.drop_table("export_artifacts")
    op.drop_table("export_requests")
