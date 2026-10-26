"""Expose the tenant's existing Stripe sandbox customer to Checkout preparation.

Revision ID: 20261025_0062
Revises: 20261025_0061
"""

from alembic import op

revision = "20261025_0062"
down_revision = "20261025_0061"
branch_labels = None
depends_on = None

_FUNCTION = "app_private.tenant_stripe_customer_reference()"


def upgrade() -> None:
    op.execute(
        r"""
        CREATE FUNCTION app_private.tenant_stripe_customer_reference()
        RETURNS text LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_org uuid:=app_private.current_organization_id();
          v_actor uuid:=app_private.current_actor_id();
          v_reference text;
        BEGIN
          IF v_org IS NULL OR v_actor IS NULL OR NOT EXISTS (
            SELECT 1 FROM public.memberships m JOIN public.organizations o ON o.id=m.organization_id
            WHERE m.organization_id=v_org AND m.user_id=v_actor AND m.status='active'
              AND m.role='admin' AND o.status='active'
          ) THEN RETURN NULL; END IF;
          SELECT provider_customer_reference INTO v_reference
          FROM public.billing_customers
          WHERE organization_id=v_org AND provider='stripe';
          RETURN v_reference;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_FUNCTION} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_FUNCTION} TO prospect_app")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_FUNCTION} FROM prospect_app")
    op.execute(f"DROP FUNCTION {_FUNCTION}")
