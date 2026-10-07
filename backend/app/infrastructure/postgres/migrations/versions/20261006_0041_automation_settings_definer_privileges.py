"""Allow the guarded Automation settings function to mutate its table."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261006_0041"
down_revision: str | None = "20261006_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The web role remains read-only.  Only the SECURITY DEFINER function from
    # 0040 receives the minimum DML required for the audited state transition.
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.automation_organization_settings TO prospect_rls_definer")


def downgrade() -> None:
    op.execute("REVOKE INSERT, UPDATE ON TABLE public.automation_organization_settings FROM prospect_rls_definer")
    op.execute("REVOKE SELECT ON TABLE public.automation_organization_settings FROM prospect_rls_definer")
