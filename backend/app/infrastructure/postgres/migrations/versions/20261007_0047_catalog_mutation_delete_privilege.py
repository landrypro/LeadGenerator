"""Let the catalog mutation definer release rejected idempotency reservations."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261007_0047"
down_revision: str | Sequence[str] | None = "20261007_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The SECURITY DEFINER wrapper deletes its operation row when a mutation is
    # rejected (for example, a creator attempting their own publication).
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.catalog_mutation_operations TO prospect_rls_definer")


def downgrade() -> None:
    op.execute("REVOKE DELETE ON public.catalog_mutation_operations FROM prospect_rls_definer")
