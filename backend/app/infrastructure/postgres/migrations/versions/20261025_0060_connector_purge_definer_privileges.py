"""Droits minimaux du défineur pour la purge des ingestions connecteur.

Revision ID: 20261025_0060
Revises: 20261024_0059
"""

from alembic import op

revision = "20261025_0060"
down_revision = "20261024_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Permettre à la fonction SECURITY DEFINER de purger sa table cible."""

    op.execute("GRANT SELECT, UPDATE ON TABLE public.connector_ingestions TO prospect_rls_definer")


def downgrade() -> None:
    op.execute("REVOKE SELECT, UPDATE ON TABLE public.connector_ingestions FROM prospect_rls_definer")
