"""Create tenant-isolated Automation admissions for IMP-A3.

Revision ID: 20261002_0033
Revises: 20261002_0032
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0033"
down_revision: str | None = "20261002_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_admissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("prospect_id", sa.Uuid(), nullable=False),
        sa.Column("playbook_version_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("preflight_id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid()),
        sa.Column("job_id", sa.Uuid()),
        sa.Column("functional_identity_fingerprint", sa.String(64), nullable=False),
        sa.Column("idempotency_key_digest", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default=sa.text("'accepted'")),
        sa.Column("result_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "id", name="uq_automation_admissions_org_id"),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key_digest", name="uq_automation_admissions_org_idempotency"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "prospect_id",
            "playbook_version_id",
            "functional_identity_fingerprint",
            name="uq_automation_admissions_functional_identity",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "playbook_version_id"],
            ["automation_playbook_versions.organization_id", "automation_playbook_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "requested_by_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "preflight_id"],
            ["automation_preflights.organization_id", "automation_preflights.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "decision_id"],
            ["automation_decisions.organization_id", "automation_decisions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "task_id"], ["prospect_tasks.organization_id", "prospect_tasks.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "job_id"], ["jobs.organization_id", "jobs.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "state IN ('accepted','preflight_required','ready_to_prepare','prepared','blocked','quarantined','to_verify','rejected','cancelled')",
            name="ck_automation_admissions_state",
        ),
        sa.CheckConstraint(
            "functional_identity_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_automation_admissions_functional_identity"
        ),
        sa.CheckConstraint("idempotency_key_digest ~ '^[a-f0-9]{64}$'", name="ck_automation_admissions_idempotency"),
        sa.CheckConstraint("request_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_automation_admissions_request"),
    )
    op.create_index(
        "ix_automation_admissions_org_state_created",
        "automation_admissions",
        ["organization_id", "state", "created_at"],
    )
    op.create_index(
        "ix_automation_admissions_org_prospect",
        "automation_admissions",
        ["organization_id", "prospect_id", "created_at"],
    )
    op.execute("ALTER TABLE public.automation_admissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.automation_admissions FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY automation_admissions_tenant_read ON public.automation_admissions FOR SELECT TO prospect_app
        USING (organization_id = app_private.current_organization_id())
    """)
    op.execute("REVOKE ALL ON public.automation_admissions FROM PUBLIC")
    op.execute("GRANT SELECT ON public.automation_admissions TO prospect_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS automation_admissions_tenant_read ON public.automation_admissions")
    op.execute("REVOKE ALL ON public.automation_admissions FROM prospect_app")
    op.execute("ALTER TABLE public.automation_admissions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.automation_admissions DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_automation_admissions_org_prospect", table_name="automation_admissions")
    op.drop_index("ix_automation_admissions_org_state_created", table_name="automation_admissions")
    op.drop_table("automation_admissions")
