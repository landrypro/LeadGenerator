"""Ajouter le profil CRM editable des prospects.

Revision ID: 20260814_0012
Revises: 20260814_0011
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0012"
down_revision: str | None = "20260814_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("profile_provenance_id", sa.Uuid(), nullable=True))
    op.add_column("prospects", sa.Column("industry_label", sa.String(length=120), nullable=True))
    op.add_column(
        "prospects",
        sa.Column("segment_code", sa.String(length=16), server_default=sa.text("'unspecified'"), nullable=False),
    )
    op.add_column(
        "prospects", sa.Column("size_band", sa.String(length=16), server_default=sa.text("'unknown'"), nullable=False)
    )
    op.add_column("prospects", sa.Column("address_line_1", sa.String(length=160), nullable=True))
    op.add_column("prospects", sa.Column("address_line_2", sa.String(length=160), nullable=True))
    op.add_column("prospects", sa.Column("city", sa.String(length=120), nullable=True))
    op.add_column("prospects", sa.Column("region", sa.String(length=120), nullable=True))
    op.add_column("prospects", sa.Column("postal_code", sa.String(length=32), nullable=True))
    op.add_column("prospects", sa.Column("country_code", sa.String(length=2), nullable=True))
    op.add_column(
        "prospects",
        sa.Column(
            "tags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
    )
    op.create_foreign_key(
        op.f("fk_prospects_organization_id_profile_provenance_id_provenance_records"),
        "prospects",
        "provenance_records",
        ["organization_id", "profile_provenance_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_prospects_segment_code_allowed"),
        "prospects",
        "segment_code IN ('unspecified', 'micro', 'small', 'medium', 'enterprise')",
    )
    op.create_check_constraint(
        op.f("ck_prospects_size_band_allowed"),
        "prospects",
        "size_band IN ('unknown', 'solo', '2_10', '11_50', '51_200', '201_plus')",
    )
    op.create_check_constraint(
        op.f("ck_prospects_country_code_format"),
        "prospects",
        "country_code IS NULL OR country_code ~ '^[A-Z]{2}$'",
    )
    op.create_check_constraint(
        op.f("ck_prospects_tags_array"),
        "prospects",
        "tags IS NOT NULL AND jsonb_typeof(tags) = 'array' AND jsonb_array_length(tags) <= 20",
    )
    op.create_index("ix_prospects_organization_archived", "prospects", ["organization_id", "archived_at"])
    op.create_index("ix_prospects_organization_updated", "prospects", ["organization_id", "updated_at"])


def downgrade() -> None:
    op.execute(
        """
        DO $checks$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.prospects
                WHERE profile_provenance_id IS NOT NULL
                   OR industry_label IS NOT NULL
                   OR segment_code <> 'unspecified'
                   OR size_band <> 'unknown'
                   OR address_line_1 IS NOT NULL
                   OR address_line_2 IS NOT NULL
                   OR city IS NOT NULL
                   OR region IS NOT NULL
                   OR postal_code IS NOT NULL
                   OR country_code IS NOT NULL
                   OR tags <> '[]'::jsonb
            ) THEN
                RAISE EXCEPTION 'Le downgrade 0012 refuse de perdre des profils CRM enrichis.';
            END IF;
        END
        $checks$;
        """
    )
    op.drop_index("ix_prospects_organization_updated", table_name="prospects")
    op.drop_index("ix_prospects_organization_archived", table_name="prospects")
    op.drop_constraint(op.f("ck_prospects_tags_array"), "prospects", type_="check")
    op.drop_constraint(op.f("ck_prospects_country_code_format"), "prospects", type_="check")
    op.drop_constraint(op.f("ck_prospects_size_band_allowed"), "prospects", type_="check")
    op.drop_constraint(op.f("ck_prospects_segment_code_allowed"), "prospects", type_="check")
    op.drop_constraint(
        op.f("fk_prospects_organization_id_profile_provenance_id_provenance_records"), "prospects", type_="foreignkey"
    )
    for column_name in (
        "tags",
        "country_code",
        "postal_code",
        "region",
        "city",
        "address_line_2",
        "address_line_1",
        "size_band",
        "segment_code",
        "industry_label",
        "profile_provenance_id",
    ):
        op.drop_column("prospects", column_name)
