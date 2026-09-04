"""Corriger les privileges du declencheur des permissions de contact.

Revision ID: 20260815_0013
Revises: 20260814_0012
Create Date: 2026-08-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260815_0013"
down_revision: str | None = "20260814_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ON CONFLICT doit pouvoir examiner la contrainte d'unicite avant le DO NOTHING.
    op.execute("GRANT SELECT ON TABLE public.contact_permissions TO prospect_rls_definer")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON TABLE public.contact_permissions FROM prospect_rls_definer")
