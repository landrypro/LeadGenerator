"""Aligner les limites textuelles des activités et tâches avec la spécification 3.3.

Revision ID: 20260905_0018
Revises: 20260905_0017
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0018"
down_revision: str | None = "20260905_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_prospect_activities_summary_length"),
        "prospect_activities",
        type_="check",
    )
    op.alter_column(
        "prospect_activities",
        "summary",
        existing_type=sa.String(length=200),
        type_=sa.String(length=160),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_prospect_activities_summary_length"),
        "prospect_activities",
        "char_length(summary) BETWEEN 1 AND 160",
    )

    op.drop_constraint(
        op.f("ck_prospect_tasks_title_length"),
        "prospect_tasks",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_prospect_tasks_description_length"),
        "prospect_tasks",
        type_="check",
    )
    op.alter_column(
        "prospect_tasks",
        "title",
        existing_type=sa.String(length=200),
        type_=sa.String(length=160),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_prospect_tasks_title_length"),
        "prospect_tasks",
        "char_length(title) BETWEEN 1 AND 160",
    )
    op.create_check_constraint(
        op.f("ck_prospect_tasks_description_length"),
        "prospect_tasks",
        "description IS NULL OR char_length(description) BETWEEN 1 AND 2000",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_prospect_tasks_description_length"),
        "prospect_tasks",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_prospect_tasks_title_length"),
        "prospect_tasks",
        type_="check",
    )
    op.alter_column(
        "prospect_tasks",
        "title",
        existing_type=sa.String(length=160),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_prospect_tasks_title_length"),
        "prospect_tasks",
        "char_length(title) BETWEEN 1 AND 200",
    )
    op.create_check_constraint(
        op.f("ck_prospect_tasks_description_length"),
        "prospect_tasks",
        "description IS NULL OR char_length(description) BETWEEN 1 AND 4000",
    )

    op.drop_constraint(
        op.f("ck_prospect_activities_summary_length"),
        "prospect_activities",
        type_="check",
    )
    op.alter_column(
        "prospect_activities",
        "summary",
        existing_type=sa.String(length=160),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_prospect_activities_summary_length"),
        "prospect_activities",
        "char_length(summary) BETWEEN 1 AND 200",
    )
