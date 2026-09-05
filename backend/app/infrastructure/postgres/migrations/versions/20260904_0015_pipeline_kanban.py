"""Ajouter le pipeline Kanban, ses étapes par organisation et son historique.

Revision ID: 20260904_0015
Revises: 20260826_0014
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260904_0015"
down_revision: str | None = "20260826_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STAGES = "'new', 'qualifying', 'qualified', 'contacted', 'opportunity', 'proposal_sent', 'negotiation', 'won', 'lost'"


def upgrade() -> None:
    # The original constraint was created with ``op.f(...)`` in 0009.  The
    # naming convention therefore materialises it as
    # ``ck_prospects_stage_code_allowed``.  Reusing ``op.f`` here prevents
    # Alembic from applying the convention a second time to the explicit
    # constraint name (which would produce ``ck_prospects_ck_prospects...``).
    op.drop_constraint(op.f("ck_prospects_stage_code_allowed"), "prospects", type_="check")
    op.create_check_constraint(
        op.f("ck_prospects_stage_code_allowed"),
        "prospects",
        f"stage_code IN ({_STAGES}, 'archived')",
    )
    op.add_column("prospects", sa.Column("stage_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE public.prospects SET stage_changed_at = updated_at WHERE stage_changed_at IS NULL")

    op.create_table(
        "pipeline_stage_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_code", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("color_token", sa.String(length=32), nullable=False),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(f"stage_code IN ({_STAGES})", name="ck_pipeline_stage_settings_stage_code_allowed"),
        sa.CheckConstraint("position BETWEEN 1 AND 9", name="ck_pipeline_stage_settings_position_range"),
        sa.CheckConstraint(
            "char_length(color_token) BETWEEN 1 AND 32", name="ck_pipeline_stage_settings_color_token_length"
        ),
        sa.CheckConstraint(
            "labels IS NOT NULL AND jsonb_typeof(labels) = 'object'", name="ck_pipeline_stage_settings_labels_object"
        ),
        sa.CheckConstraint("version > 0", name="ck_pipeline_stage_settings_version_positive"),
        sa.UniqueConstraint("organization_id", "stage_code", name="uq_pipeline_stage_settings_organization_stage"),
        sa.UniqueConstraint("organization_id", "position", name="uq_pipeline_stage_settings_organization_position"),
    )
    op.create_table(
        "prospect_stage_transitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prospect_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("from_stage", sa.String(length=32), nullable=False),
        sa.Column("to_stage", sa.String(length=32), nullable=False),
        sa.Column("from_version", sa.Integer(), nullable=False),
        sa.Column("resulting_version", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("reason_note", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("command_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "prospect_id"], ["prospects.organization_id", "prospects.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(f"from_stage IN ({_STAGES})", name="ck_prospect_stage_transitions_from_stage_allowed"),
        sa.CheckConstraint(f"to_stage IN ({_STAGES})", name="ck_prospect_stage_transitions_to_stage_allowed"),
        sa.CheckConstraint("from_stage <> to_stage", name="ck_prospect_stage_transitions_stage_changed"),
        sa.CheckConstraint(
            "from_version > 0 AND resulting_version > from_version",
            name="ck_prospect_stage_transitions_version_sequence",
        ),
        sa.CheckConstraint(
            "reason_note IS NULL OR char_length(reason_note) BETWEEN 1 AND 500",
            name="ck_prospect_stage_transitions_reason_note_length",
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_prospect_stage_transitions_organization_id_id"),
        sa.UniqueConstraint(
            "organization_id", "prospect_id", "idempotency_key", name="uq_prospect_stage_transitions_idempotency"
        ),
    )
    op.create_index(
        "ix_prospect_stage_transitions_organization_prospect_occurred",
        "prospect_stage_transitions",
        ["organization_id", "prospect_id", "occurred_at"],
    )

    op.execute(
        """
        INSERT INTO public.pipeline_stage_settings (
            id, organization_id, stage_code, position, color_token, labels, created_at, updated_at
        )
        SELECT gen_random_uuid(), organization.id, stage.stage_code, stage.position, stage.color_token,
               stage.labels::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM public.organizations AS organization
        CROSS JOIN (
            VALUES
              ('new', 1, 'slate', '{"fr-CA":"Nouveau","en-CA":"New"}'),
              ('qualifying', 2, 'blue', '{"fr-CA":"Qualification","en-CA":"Qualifying"}'),
              ('qualified', 3, 'indigo', '{"fr-CA":"Qualifié","en-CA":"Qualified"}'),
              ('contacted', 4, 'cyan', '{"fr-CA":"Contacté","en-CA":"Contacted"}'),
              ('opportunity', 5, 'violet', '{"fr-CA":"Opportunité","en-CA":"Opportunity"}'),
              ('proposal_sent', 6, 'amber', '{"fr-CA":"Soumission envoyée","en-CA":"Proposal sent"}'),
              ('negotiation', 7, 'orange', '{"fr-CA":"Négociation","en-CA":"Negotiation"}'),
              ('won', 8, 'green', '{"fr-CA":"Gagné","en-CA":"Won"}'),
              ('lost', 9, 'red', '{"fr-CA":"Perdu","en-CA":"Lost"}')
        ) AS stage(stage_code, position, color_token, labels)
        """
    )

    for table in ("pipeline_stage_settings", "prospect_stage_transitions"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON public.{table} "
            "USING (organization_id = app_private.current_organization_id()) "
            "WITH CHECK (organization_id = app_private.current_organization_id())"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.{table} TO prospect_app")


def downgrade() -> None:
    for table in ("prospect_stage_transitions", "pipeline_stage_settings"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON public.{table}")
        op.drop_table(table)
    op.drop_column("prospects", "stage_changed_at")
    op.drop_constraint(op.f("ck_prospects_stage_code_allowed"), "prospects", type_="check")
    op.create_check_constraint(
        op.f("ck_prospects_stage_code_allowed"),
        "prospects",
        "stage_code IN ('new', 'qualified', 'contacted', 'proposal_sent', 'won', 'lost', 'archived')",
    )
