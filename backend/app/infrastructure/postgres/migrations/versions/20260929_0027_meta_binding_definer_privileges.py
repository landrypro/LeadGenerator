"""Grant the Meta binding resolver its narrowly scoped definer reads.

Revision ID: 20260929_0027
Revises: 20260925_0026
"""

from alembic import op

revision = "20260929_0027"
down_revision = "20260925_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # resolve_meta_lead_binding is SECURITY DEFINER and must resolve an inbound,
    # signed webhook before a tenant context exists. The definer is BYPASSRLS but
    # still needs explicit SELECT privileges on every table used by the function.
    op.execute("""
        GRANT SELECT ON TABLE
            public.provider_connector_contracts,
            public.provider_connector_bindings,
            public.source_providers,
            public.acquisition_records,
            public.memberships,
            public.users
        TO prospect_rls_definer
    """)


def downgrade() -> None:
    # acquisition_records and memberships already grant this role SELECT through
    # earlier migrations and must keep those permissions when this fix is rolled back.
    op.execute("""
        REVOKE SELECT ON TABLE
            public.provider_connector_contracts,
            public.provider_connector_bindings,
            public.source_providers,
            public.users
        FROM prospect_rls_definer
    """)
