"""Ajouter le socle persistant des opportunités CRM.

Revision ID: 20260910_0020
Revises: 20260905_0019
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0020"
down_revision: str | None = "20260905_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OPEN_STAGES = "'discovery', 'qualification', 'proposal', 'negotiation'"
_ALL_STAGES = f"{_OPEN_STAGES}, 'won', 'lost'"
_LOSS_REASONS = (
    "'no_need', 'no_budget', 'no_response', 'competitor', 'timing', 'scope_mismatch', 'invalid_or_duplicate', 'other'"
)
_TABLES = ("opportunities", "opportunity_events")


def upgrade() -> None:
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prospect_id", sa.Uuid(), nullable=False),
        sa.Column("owner_membership_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("currency_code", sa.CHAR(length=3), nullable=False),
        sa.Column("probability", sa.SmallInteger(), nullable=False, server_default="10"),
        sa.Column("stage_code", sa.String(length=32), nullable=False, server_default=sa.text("'discovery'")),
        sa.Column("expected_close_on", sa.Date(), nullable=False),
        sa.Column("loss_reason_code", sa.String(length=64), nullable=True),
        sa.Column("loss_reason_note", sa.String(length=500), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "owner_membership_id"],
            ["memberships.organization_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 160", name=op.f("ck_opportunities_name_length")),
        sa.CheckConstraint(
            "amount > 0 AND amount <> 'NaN'::numeric", name=op.f("ck_opportunities_amount_positive_and_finite")
        ),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name=op.f("ck_opportunities_currency_format")),
        sa.CheckConstraint("probability BETWEEN 0 AND 100", name=op.f("ck_opportunities_probability_range")),
        sa.CheckConstraint(f"stage_code IN ({_ALL_STAGES})", name=op.f("ck_opportunities_stage_code_allowed")),
        sa.CheckConstraint("version > 0", name=op.f("ck_opportunities_version_positive")),
        sa.CheckConstraint(
            "loss_reason_note IS NULL OR char_length(loss_reason_note) BETWEEN 1 AND 500",
            name=op.f("ck_opportunities_loss_reason_note_length"),
        ),
        sa.CheckConstraint(
            f"""
            (
                stage_code IN ({_OPEN_STAGES})
                AND closed_at IS NULL
                AND loss_reason_code IS NULL
                AND loss_reason_note IS NULL
            )
            OR (
                stage_code = 'won'
                AND probability = 100
                AND closed_at IS NOT NULL
                AND loss_reason_code IS NULL
                AND loss_reason_note IS NULL
            )
            OR (
                stage_code = 'lost'
                AND probability = 0
                AND closed_at IS NOT NULL
                AND loss_reason_code IN ({_LOSS_REASONS})
                AND (loss_reason_code <> 'other' OR loss_reason_note IS NOT NULL)
            )
            """,
            name=op.f("ck_opportunities_terminal_state_consistency"),
        ),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_opportunities_organization_id_id")),
        sa.UniqueConstraint(
            "organization_id", "prospect_id", "id", name=op.f("uq_opportunities_organization_prospect_id")
        ),
    )
    op.create_index(
        "ix_opportunities_organization_prospect_stage_expected_close",
        "opportunities",
        ["organization_id", "prospect_id", "stage_code", "expected_close_on", "id"],
    )
    op.create_index(
        "ix_opportunities_organization_owner_stage_expected_close",
        "opportunities",
        ["organization_id", "owner_membership_id", "stage_code", "expected_close_on", "id"],
    )
    op.create_index(
        "ix_opportunities_open_expected_close",
        "opportunities",
        ["organization_id", "expected_close_on", "id"],
        postgresql_where=sa.text(f"stage_code IN ({_OPEN_STAGES})"),
    )

    op.create_table(
        "opportunity_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prospect_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("from_stage", sa.String(length=32), nullable=True),
        sa.Column("to_stage", sa.String(length=32), nullable=True),
        sa.Column("from_version", sa.Integer(), nullable=False),
        sa.Column("resulting_version", sa.Integer(), nullable=False),
        sa.Column(
            "changed_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("reason_note", sa.String(length=500), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("command_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "prospect_id", "opportunity_id"],
            ["opportunities.organization_id", "opportunities.prospect_id", "opportunities.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "event_type IN ('created', 'updated', 'stage_changed', 'reopened')",
            name=op.f("ck_opportunity_events_event_type_allowed"),
        ),
        sa.CheckConstraint(
            f"from_stage IS NULL OR from_stage IN ({_ALL_STAGES})",
            name=op.f("ck_opportunity_events_from_stage_allowed"),
        ),
        sa.CheckConstraint(
            f"to_stage IS NULL OR to_stage IN ({_ALL_STAGES})",
            name=op.f("ck_opportunity_events_to_stage_allowed"),
        ),
        sa.CheckConstraint(
            """
            (event_type = 'created' AND from_stage IS NULL AND to_stage = 'discovery'
             AND from_version = 1 AND resulting_version = 1)
            OR (event_type = 'updated' AND from_stage IS NULL AND to_stage IS NULL
                AND from_version > 0 AND resulting_version > from_version)
            OR (event_type IN ('stage_changed', 'reopened') AND from_stage IS NOT NULL AND to_stage IS NOT NULL
                AND from_stage <> to_stage AND from_version > 0 AND resulting_version > from_version)
            """,
            name=op.f("ck_opportunity_events_event_shape_consistency"),
        ),
        sa.CheckConstraint(
            "changed_fields IS NOT NULL AND jsonb_typeof(changed_fields) = 'object'",
            name=op.f("ck_opportunity_events_changed_fields_object"),
        ),
        sa.CheckConstraint(
            "reason_note IS NULL OR char_length(reason_note) BETWEEN 1 AND 500",
            name=op.f("ck_opportunity_events_reason_note_length"),
        ),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_opportunity_events_organization_id_id")),
        sa.UniqueConstraint(
            "organization_id", "event_type", "idempotency_key", name=op.f("uq_opportunity_events_idempotency")
        ),
    )
    op.create_index(
        "ix_opportunity_events_organization_opportunity_occurred",
        "opportunity_events",
        ["organization_id", "opportunity_id", sa.text("occurred_at DESC"), sa.text("id DESC")],
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

    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.opportunities TO prospect_app")
    op.execute("GRANT SELECT, INSERT ON TABLE public.opportunity_events TO prospect_app")


def downgrade() -> None:
    for table_name in reversed(_TABLES):
        op.drop_table(table_name)
