"""Create isolated, disabled-by-default Automation foundations.

Revision ID: 20261002_0031
Revises: 20260929_0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20261002_0031"
down_revision: str | None = "20260929_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTOMATION_TABLES = (
    "automation_organization_settings",
    "automation_playbooks",
    "automation_playbook_versions",
    "automation_decisions",
    "automation_exceptions",
)


def _enable_read_only_tenant_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY {table_name}_tenant_read ON public.{table_name} FOR SELECT TO prospect_app
        USING (organization_id = app_private.current_organization_id())
    """)
    op.execute(f"REVOKE ALL ON public.{table_name} FROM PUBLIC")
    op.execute(f"GRANT SELECT ON public.{table_name} TO prospect_app")


def upgrade() -> None:
    op.create_table(
        "automation_organization_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("automation_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("suspension_generation", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint("organization_id", name="uq_automation_settings_organization"),
        sa.CheckConstraint("suspension_generation >= 0", name="ck_automation_settings_suspension_generation"),
        sa.CheckConstraint("version > 0", name="ck_automation_settings_version"),
    )
    op.create_index(
        "ix_automation_settings_org_enabled",
        "automation_organization_settings",
        ["organization_id", "automation_enabled"],
    )

    op.create_table(
        "automation_playbooks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("prepare_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("suspension_generation", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint("organization_id", "id", name="uq_automation_playbooks_org_id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_automation_playbooks_org_code"),
        sa.CheckConstraint(
            "code IN ('new_prospect','proposal_pending','forgotten_opportunity')",
            name="ck_automation_playbooks_code",
        ),
        sa.CheckConstraint(
            "state IN ('draft','preflight_required','preflight_running','ready','active_prepare','suspended','retired')",
            name="ck_automation_playbooks_state",
        ),
        sa.CheckConstraint("suspension_generation >= 0", name="ck_automation_playbooks_suspension_generation"),
        sa.CheckConstraint("version > 0", name="ck_automation_playbooks_version"),
    )
    op.create_index("ix_automation_playbooks_org_state", "automation_playbooks", ["organization_id", "state"])

    op.create_table(
        "automation_playbook_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("playbook_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("ruleset_version", sa.String(64), nullable=False),
        sa.Column("configuration", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("snapshot_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "id", name="uq_automation_playbook_versions_org_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "playbook_id"],
            ["automation_playbooks.organization_id", "automation_playbooks.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("version_number > 0", name="ck_automation_playbook_versions_number"),
        sa.CheckConstraint(
            "snapshot_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_automation_playbook_versions_fingerprint"
        ),
        sa.CheckConstraint("jsonb_typeof(configuration) = 'object'", name="ck_automation_playbook_versions_config"),
    )
    op.create_index(
        "uq_automation_playbook_versions_org_playbook_number",
        "automation_playbook_versions",
        ["organization_id", "playbook_id", "version_number"],
        unique=True,
    )
    op.create_index(
        "ix_automation_playbook_versions_org_created",
        "automation_playbook_versions",
        ["organization_id", "created_at"],
    )

    op.create_table(
        "automation_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("playbook_version_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("fire_level", sa.String(16), nullable=False),
        sa.Column("next_action", sa.String(16), nullable=False),
        sa.Column("reason_codes", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("context_fingerprint", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "id", name="uq_automation_decisions_org_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "playbook_version_id"],
            ["automation_playbook_versions.organization_id", "automation_playbook_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("subject_type IN ('prospect','opportunity')", name="ck_automation_decisions_subject_type"),
        sa.CheckConstraint(
            "fire_level IN ('red','yellow','green','to_verify')", name="ck_automation_decisions_fire_level"
        ),
        sa.CheckConstraint("next_action IN ('refuse','verify','prepare')", name="ck_automation_decisions_next_action"),
        sa.CheckConstraint(
            "outcome IN ('prepared','refused','stale','to_verify')", name="ck_automation_decisions_outcome"
        ),
        sa.CheckConstraint(
            "context_fingerprint ~ '^[a-f0-9]{64}$'", name="ck_automation_decisions_context_fingerprint"
        ),
        sa.CheckConstraint("jsonb_typeof(reason_codes) = 'array'", name="ck_automation_decisions_reason_codes"),
        sa.CheckConstraint("expires_at > created_at", name="ck_automation_decisions_expiry"),
    )
    op.create_index(
        "ix_automation_decisions_org_subject",
        "automation_decisions",
        ["organization_id", "subject_type", "subject_id", "created_at"],
    )
    op.create_index(
        "uq_automation_decisions_org_correlation",
        "automation_decisions",
        ["organization_id", "correlation_id"],
        unique=True,
    )

    op.create_table(
        "automation_exceptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("exception_code", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default=sa.text("'open'")),
        sa.Column("assigned_membership_id", sa.Uuid(), nullable=True),
        sa.Column("resolution_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "id", name="uq_automation_exceptions_org_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "decision_id"],
            ["automation_decisions.organization_id", "automation_decisions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "assigned_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("subject_type IN ('prospect','opportunity')", name="ck_automation_exceptions_subject_type"),
        sa.CheckConstraint(
            "exception_code IN ('owner_unavailable','ambiguous_match','effect_uncertain','source_unavailable')",
            name="ck_automation_exceptions_code",
        ),
        sa.CheckConstraint(
            "state IN ('open','in_progress','resolved','abandoned')", name="ck_automation_exceptions_state"
        ),
    )
    op.create_index(
        "ix_automation_exceptions_org_state",
        "automation_exceptions",
        ["organization_id", "state", "created_at"],
    )

    for table_name in _AUTOMATION_TABLES:
        _enable_read_only_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(_AUTOMATION_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_read ON public.{table_name}")
        op.execute(f"REVOKE ALL ON public.{table_name} FROM prospect_app")
        op.execute(f"ALTER TABLE public.{table_name} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table_name} DISABLE ROW LEVEL SECURITY")

    op.drop_table("automation_exceptions")
    op.drop_table("automation_decisions")
    op.drop_table("automation_playbook_versions")
    op.drop_table("automation_playbooks")
    op.drop_table("automation_organization_settings")
