"""Corriger les valeurs par défaut textuelles des activités et tâches.

Revision ID: 20260905_0019
Revises: 20260905_0018
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0019"
down_revision: str | None = "20260905_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "prospect_activities",
        "permission_snapshot",
        existing_type=sa.String(length=32),
        server_default=sa.text("'not_applicable'"),
        existing_nullable=False,
    )
    op.alter_column(
        "prospect_tasks",
        "priority",
        existing_type=sa.String(length=16),
        server_default=sa.text("'normal'"),
        existing_nullable=False,
    )
    op.alter_column(
        "prospect_tasks",
        "status",
        existing_type=sa.String(length=16),
        server_default=sa.text("'open'"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "prospect_tasks",
        "status",
        existing_type=sa.String(length=16),
        server_default=sa.text("'''open'''"),
        existing_nullable=False,
    )
    op.alter_column(
        "prospect_tasks",
        "priority",
        existing_type=sa.String(length=16),
        server_default=sa.text("'''normal'''"),
        existing_nullable=False,
    )
    op.alter_column(
        "prospect_activities",
        "permission_snapshot",
        existing_type=sa.String(length=32),
        server_default=sa.text("'''not_applicable'''"),
        existing_nullable=False,
    )
