"""Ajouter le traitement CSV temporaire et les rapports minimisés de 3.1.

Revision ID: 20260826_0014
Revises: 20260815_0013
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260826_0014"
down_revision: str | None = "20260815_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("csv_import_sessions", "csv_import_runs", "csv_import_quarantines", "csv_import_fingerprints")


def upgrade() -> None:
    op.create_table(
        "csv_import_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("declaration_id", sa.Uuid(), nullable=False),
        sa.Column("file_ref", sa.String(length=64), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("ready_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quarantined_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["organization_id", "declaration_id"],
            ["import_declarations.organization_id", "import_declarations.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_csv_import_sessions_organization_id_id")),
        sa.CheckConstraint("content_sha256 ~ '^[a-f0-9]{64}$'", name=op.f("ck_csv_import_sessions_sha256")),
        sa.CheckConstraint("byte_size BETWEEN 1 AND 10485760", name=op.f("ck_csv_import_sessions_size")),
        sa.CheckConstraint(
            "jsonb_typeof(headers) = 'array' AND jsonb_array_length(headers) BETWEEN 1 AND 50",
            name=op.f("ck_csv_import_sessions_headers"),
        ),
        sa.CheckConstraint("jsonb_typeof(mapping) = 'object'", name=op.f("ck_csv_import_sessions_mapping")),
        sa.CheckConstraint(
            "status IN ('uploaded', 'mapped', 'validated', 'confirmed', 'expired')",
            name=op.f("ck_csv_import_sessions_status"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_csv_import_sessions_version")),
    )
    op.create_index(
        "ix_csv_import_sessions_organization_declaration", "csv_import_sessions", ["organization_id", "declaration_id"]
    )
    op.create_index("ix_csv_import_sessions_expiry", "csv_import_sessions", ["expires_at"])

    op.create_table(
        "csv_import_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("command_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("quarantined_count", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "session_id"],
            ["csv_import_sessions.organization_id", "csv_import_sessions.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_csv_import_runs_organization_id_id")),
        sa.UniqueConstraint("organization_id", "idempotency_key", name=op.f("uq_csv_import_runs_idempotency")),
        sa.CheckConstraint("command_fingerprint ~ '^[a-f0-9]{64}$'", name=op.f("ck_csv_import_runs_fingerprint")),
    )
    op.create_index("ix_csv_import_runs_organization_session", "csv_import_runs", ["organization_id", "session_id"])

    op.create_table(
        "csv_import_quarantines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("opaque_reference", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "run_id"], ["csv_import_runs.organization_id", "csv_import_runs.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("organization_id", "run_id", "line_number", name=op.f("uq_csv_import_quarantines_line")),
        sa.CheckConstraint("line_number > 1", name=op.f("ck_csv_import_quarantines_line")),
        sa.CheckConstraint("jsonb_typeof(reason_codes) = 'array'", name=op.f("ck_csv_import_quarantines_reasons")),
    )

    op.create_table(
        "csv_import_fingerprints",
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("prospect_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("organization_id", "fingerprint", name=op.f("pk_csv_import_fingerprints")),
        sa.CheckConstraint("fingerprint ~ '^[a-f0-9]{64}$'", name=op.f("ck_csv_import_fingerprints_fingerprint")),
    )

    for table_name in _TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table_name}_tenant_isolation ON public.{table_name} FOR ALL TO prospect_app
            USING (organization_id = app_private.current_organization_id())
            WITH CHECK (organization_id = app_private.current_organization_id())
        """)
        op.execute(f"REVOKE ALL ON TABLE public.{table_name} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON TABLE public.{table_name} FROM prospect_app")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{table_name} TO prospect_app")


def downgrade() -> None:
    op.drop_table("csv_import_fingerprints")
    op.drop_table("csv_import_quarantines")
    op.drop_table("csv_import_runs")
    op.drop_table("csv_import_sessions")
