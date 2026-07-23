"""Créer la révision de référence de l’infrastructure 2.1.

Revision ID: 20260722_0001
Revises:
Create Date: 2026-07-22
"""

from collections.abc import Sequence

revision: str = "20260722_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Établir la base Alembic avant les tables d’identité de l’incrément 2.2."""


def downgrade() -> None:
    """Retirer la révision de référence, qui ne crée encore aucune table métier."""
