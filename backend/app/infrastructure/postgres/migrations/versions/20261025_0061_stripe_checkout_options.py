"""Expose published sandbox Checkout offers to authorized tenant administrators.

Revision ID: 20261025_0061
Revises: 20261025_0060
"""

from alembic import op

revision = "20261025_0061"
down_revision = "20261025_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE FUNCTION app_private.tenant_stripe_checkout_options(p_now timestamptz)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_org uuid:=app_private.current_organization_id();
          v_actor uuid:=app_private.current_actor_id();
          v_options jsonb;
        BEGIN
          IF v_org IS NULL OR v_actor IS NULL OR p_now IS NULL OR NOT EXISTS (
            SELECT 1 FROM public.memberships m JOIN public.organizations o ON o.id=m.organization_id
            WHERE m.organization_id=v_org AND m.user_id=v_actor AND m.status='active'
              AND m.role='admin' AND o.status='active'
          ) THEN RETURN '[]'::jsonb; END IF;

          SELECT COALESCE(jsonb_agg(
            jsonb_build_object(
              'id', offer.id, 'code', offer.code, 'version_number', offer.version_number,
              'currency', offer.currency, 'amount_minor', offer.amount_minor,
              'billing_cycle', offer.billing_cycle
            ) ORDER BY offer.display_order, offer.code, offer.currency, offer.version_number
          ), '[]'::jsonb) INTO v_options
          FROM (
            SELECT v.id, p.code, p.display_order, v.version_number, v.currency,
                   v.amount_excluding_tax_minor AS amount_minor, v.billing_cycle
            FROM public.plan_versions v
            JOIN public.plan_catalog p ON p.id=v.plan_id
            WHERE p.state='published' AND v.state='published'
              AND v.effective_from<=p_now
              AND (v.effective_until IS NULL OR v.effective_until>p_now)
              AND v.billing_cycle='monthly' AND v.amount_excluding_tax_minor>0
              AND EXISTS (
                SELECT 1 FROM public.plan_entitlements e
                WHERE e.plan_version_id=v.id AND e.entitlement_key='seats.active_members.max'
                  AND e.value_kind='limit'
              )
              AND EXISTS (
                SELECT 1 FROM public.plan_entitlements e
                WHERE e.plan_version_id=v.id AND e.entitlement_key='seats.pending_invitations.max'
                  AND e.value_kind='limit'
              )
            ORDER BY p.display_order, p.code, v.currency, v.version_number
            LIMIT 100
          ) offer;
          RETURN v_options;
        END $fn$;
        """
    )
    signature = "app_private.tenant_stripe_checkout_options(timestamptz)"
    op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")


def downgrade() -> None:
    signature = "app_private.tenant_stripe_checkout_options(timestamptz)"
    op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM prospect_app")
    op.execute(f"DROP FUNCTION {signature}")
