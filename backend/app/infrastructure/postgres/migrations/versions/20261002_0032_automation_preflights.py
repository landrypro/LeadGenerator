"""Create tenant-isolated Automation Preflights and link decisions.

Revision ID: 20261002_0032
Revises: 20261002_0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0032"
down_revision: str | None = "20261002_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_read_only_tenant_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY {table_name}_tenant_read ON public.{table_name} FOR SELECT TO prospect_app
        USING (organization_id = app_private.current_organization_id())
    """)
    op.execute(f"REVOKE ALL ON public.{table_name} FROM PUBLIC")
    op.execute(f"GRANT SELECT ON public.{table_name} TO prospect_app")


def _disable_read_only_tenant_rls(table_name: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_read ON public.{table_name}")
    op.execute(f"REVOKE ALL ON public.{table_name} FROM prospect_app")
    op.execute(f"ALTER TABLE public.{table_name} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE public.{table_name} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    existing_decision_count = op.get_bind().execute(sa.text("SELECT count(*) FROM automation_decisions")).scalar_one()
    if existing_decision_count:
        raise RuntimeError(
            "La relation Prévol → décision exige un rattachement explicite ; "
            "aucune décision Automation existante ne peut être migrée implicitement."
        )

    op.create_table(
        "automation_preflights",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("playbook_version_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("ruleset_version", sa.String(64), nullable=False),
        sa.Column("scope_fingerprint", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("subject_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("green_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("yellow_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("red_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("to_verify_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "id", name="uq_automation_preflights_org_id"),
        sa.UniqueConstraint("organization_id", "correlation_id", name="uq_automation_preflights_org_correlation"),
        sa.ForeignKeyConstraint(
            ["organization_id", "playbook_version_id"],
            ["automation_playbook_versions.organization_id", "automation_playbook_versions.id"],
            name="fk_automation_preflights_org_playbook_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "requested_by_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_automation_preflights_org_requester",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "state IN ('queued','running','completed','needs_review','failed','stale','cancelled')",
            name="ck_automation_preflights_state",
        ),
        sa.CheckConstraint("scope_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_automation_preflights_scope_fingerprint"),
        sa.CheckConstraint("subject_count >= 0", name="ck_automation_preflights_subject_count"),
        sa.CheckConstraint("green_count >= 0", name="ck_automation_preflights_green_count"),
        sa.CheckConstraint("yellow_count >= 0", name="ck_automation_preflights_yellow_count"),
        sa.CheckConstraint("red_count >= 0", name="ck_automation_preflights_red_count"),
        sa.CheckConstraint("to_verify_count >= 0", name="ck_automation_preflights_to_verify_count"),
        sa.CheckConstraint("expires_at > created_at", name="ck_automation_preflights_expiry"),
    )
    op.create_index(
        "ix_automation_preflights_org_state_created",
        "automation_preflights",
        ["organization_id", "state", "created_at"],
    )
    _enable_read_only_tenant_rls("automation_preflights")

    op.add_column("automation_decisions", sa.Column("preflight_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_automation_decisions_org_preflight",
        "automation_decisions",
        "automation_preflights",
        ["organization_id", "preflight_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_automation_decisions_org_preflight_subject",
        "automation_decisions",
        ["organization_id", "preflight_id", "subject_type", "subject_id"],
    )
    op.create_index(
        "ix_automation_decisions_org_preflight",
        "automation_decisions",
        ["organization_id", "preflight_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_automation_decisions_org_preflight", table_name="automation_decisions")
    op.drop_constraint(
        "uq_automation_decisions_org_preflight_subject",
        "automation_decisions",
        type_="unique",
    )
    op.drop_constraint("fk_automation_decisions_org_preflight", "automation_decisions", type_="foreignkey")
    op.drop_column("automation_decisions", "preflight_id")

    _disable_read_only_tenant_rls("automation_preflights")
    op.drop_table("automation_preflights")
