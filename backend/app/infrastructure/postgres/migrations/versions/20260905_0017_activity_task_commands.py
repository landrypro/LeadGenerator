"""Ajouter l’idempotence des commandes de tâches CRM.

Revision ID: 20260905_0017
Revises: 20260905_0016
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0017"
down_revision: str | None = "20260905_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_prospect_task_events_event_type_allowed"), "prospect_task_events", type_="check")
    op.create_check_constraint(
        op.f("ck_prospect_task_events_event_type_allowed"),
        "prospect_task_events",
        "event_type IN ('created', 'updated', 'completed', 'cancelled', 'reopened', 'reminder_acknowledged', 'reminder_snoozed')",
    )
    op.add_column("prospect_tasks", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("prospect_tasks", sa.Column("command_fingerprint", sa.String(length=128), nullable=True))
    op.create_index(
        "uq_prospect_tasks_idempotency",
        "prospect_tasks",
        ["organization_id", "prospect_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.add_column("prospect_task_events", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("prospect_task_events", sa.Column("command_fingerprint", sa.String(length=128), nullable=True))
    op.create_index(
        "uq_prospect_task_events_idempotency",
        "prospect_task_events",
        ["organization_id", "task_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_prospect_task_events_idempotency", table_name="prospect_task_events")
    op.drop_column("prospect_task_events", "command_fingerprint")
    op.drop_column("prospect_task_events", "idempotency_key")
    op.drop_index("uq_prospect_tasks_idempotency", table_name="prospect_tasks")
    op.drop_column("prospect_tasks", "command_fingerprint")
    op.drop_column("prospect_tasks", "idempotency_key")
    op.drop_constraint(op.f("ck_prospect_task_events_event_type_allowed"), "prospect_task_events", type_="check")
    op.create_check_constraint(
        op.f("ck_prospect_task_events_event_type_allowed"),
        "prospect_task_events",
        "event_type IN ('created', 'updated', 'completed', 'cancelled', 'reminder_acknowledged', 'reminder_snoozed')",
    )
