"""Ajouter le socle des activités, tâches, événements et rappels CRM.

Revision ID: 20260905_0016
Revises: 20260904_0015
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260905_0016"
down_revision: str | None = "20260904_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("prospect_activities", "prospect_tasks", "prospect_task_events")


def upgrade() -> None:
    op.create_table(
        "prospect_activities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prospect_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.String(length=200), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("contact_channel_id", sa.Uuid(), nullable=True),
        sa.Column("permission_snapshot", sa.String(length=32), nullable=False, server_default="'not_applicable'"),
        sa.Column("correction_of_activity_id", sa.Uuid(), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("command_fingerprint", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "contact_id"], ["contacts.organization_id", "contacts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "contact_channel_id"],
            ["contact_channels.organization_id", "contact_channels.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "correction_of_activity_id"],
            ["prospect_activities.organization_id", "prospect_activities.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_prospect_activities_organization_id_id")),
        sa.CheckConstraint(
            "activity_type IN ('note', 'call', 'email', 'meeting')",
            name=op.f("ck_prospect_activities_activity_type_allowed"),
        ),
        sa.CheckConstraint(
            "direction IN ('internal', 'inbound', 'outbound')", name=op.f("ck_prospect_activities_direction_allowed")
        ),
        sa.CheckConstraint(
            "char_length(summary) BETWEEN 1 AND 200", name=op.f("ck_prospect_activities_summary_length")
        ),
        sa.CheckConstraint(
            "note IS NULL OR char_length(note) BETWEEN 1 AND 4000", name=op.f("ck_prospect_activities_note_length")
        ),
        sa.CheckConstraint(
            "permission_snapshot IN ('unknown', 'allowed', 'restricted', 'not_applicable')",
            name=op.f("ck_prospect_activities_permission_snapshot_allowed"),
        ),
        sa.CheckConstraint(
            "(correction_of_activity_id IS NULL) = (correction_reason IS NULL)",
            name=op.f("ck_prospect_activities_correction_pair"),
        ),
        sa.CheckConstraint(
            "correction_reason IS NULL OR char_length(correction_reason) BETWEEN 1 AND 500",
            name=op.f("ck_prospect_activities_correction_reason_length"),
        ),
    )
    op.create_index(
        "ix_prospect_activities_organization_prospect_occurred",
        "prospect_activities",
        ["organization_id", "prospect_id", "occurred_at"],
    )
    op.create_index(
        "ix_prospect_activities_organization_actor_occurred",
        "prospect_activities",
        ["organization_id", "actor_id", "occurred_at"],
    )
    op.create_index(
        "uq_prospect_activities_idempotency",
        "prospect_activities",
        ["organization_id", "prospect_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "prospect_tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prospect_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_membership_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="'normal'"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="'open'"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "assigned_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_prospect_tasks_organization_id_id")),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 200", name=op.f("ck_prospect_tasks_title_length")),
        sa.CheckConstraint(
            "description IS NULL OR char_length(description) BETWEEN 1 AND 4000",
            name=op.f("ck_prospect_tasks_description_length"),
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')", name=op.f("ck_prospect_tasks_priority_allowed")
        ),
        sa.CheckConstraint(
            "status IN ('open', 'completed', 'cancelled')", name=op.f("ck_prospect_tasks_status_allowed")
        ),
        sa.CheckConstraint(
            "reminder_at IS NULL OR reminder_at <= due_at", name=op.f("ck_prospect_tasks_reminder_before_due")
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_prospect_tasks_version_positive")),
    )
    op.create_index(
        "ix_prospect_tasks_organization_prospect_due", "prospect_tasks", ["organization_id", "prospect_id", "due_at"]
    )
    op.create_index(
        "ix_prospect_tasks_organization_assignee_status_due",
        "prospect_tasks",
        ["organization_id", "assigned_membership_id", "status", "due_at"],
    )

    op.create_table(
        "prospect_task_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prospect_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("resulting_status", sa.String(length=16), nullable=False),
        sa.Column("resulting_version", sa.Integer(), nullable=False),
        sa.Column(
            "changed_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "task_id"], ["prospect_tasks.organization_id", "prospect_tasks.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_prospect_task_events_organization_id_id")),
        sa.CheckConstraint(
            "event_type IN ('created', 'updated', 'completed', 'cancelled', 'reminder_acknowledged', 'reminder_snoozed')",
            name=op.f("ck_prospect_task_events_event_type_allowed"),
        ),
        sa.CheckConstraint(
            "resulting_status IN ('open', 'completed', 'cancelled')",
            name=op.f("ck_prospect_task_events_resulting_status_allowed"),
        ),
        sa.CheckConstraint("resulting_version > 0", name=op.f("ck_prospect_task_events_resulting_version_positive")),
        sa.CheckConstraint(
            "changed_fields IS NOT NULL AND jsonb_typeof(changed_fields) = 'object'",
            name=op.f("ck_prospect_task_events_changed_fields_object"),
        ),
        sa.CheckConstraint(
            "reason IS NULL OR char_length(reason) BETWEEN 1 AND 500",
            name=op.f("ck_prospect_task_events_reason_length"),
        ),
    )
    op.create_index(
        "ix_prospect_task_events_organization_task_occurred",
        "prospect_task_events",
        ["organization_id", "task_id", "occurred_at"],
    )

    for table_name in _TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation ON public.{table_name} FOR ALL TO prospect_app
            USING (organization_id = app_private.current_organization_id())
            WITH CHECK (organization_id = app_private.current_organization_id())
            """
        )
        op.execute(f"REVOKE ALL ON TABLE public.{table_name} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON TABLE public.{table_name} FROM prospect_app")

    op.execute("GRANT SELECT, INSERT ON TABLE public.prospect_activities TO prospect_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.prospect_tasks TO prospect_app")
    op.execute("GRANT SELECT, INSERT ON TABLE public.prospect_task_events TO prospect_app")


def downgrade() -> None:
    for table_name in reversed(_TABLES):
        op.drop_table(table_name)
