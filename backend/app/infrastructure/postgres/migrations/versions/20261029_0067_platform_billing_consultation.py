"""Expose a platform-safe, read-only Billing projection (P53-10 DEV-04)."""

from alembic import op

revision = "20261029_0067"
down_revision = "20261028_0066"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "app_private.list_platform_billing_organizations(uuid,integer,text,text)",
    "app_private.get_platform_billing_organization(uuid)",
)


def upgrade() -> None:
    # These functions deliberately return only business-safe projection fields.
    # Provider customer/subscription/event identifiers and normalized payloads
    # remain inaccessible to the platform UI.
    op.execute(r"""
        CREATE FUNCTION app_private.list_platform_billing_organizations(
          p_after uuid,p_limit integer,p_state text,p_source text
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_payload jsonb;
        BEGIN
          IF v_actor IS NULL OR NOT EXISTS(
            SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin'
          ) THEN RAISE EXCEPTION 'platform_billing_forbidden' USING ERRCODE='42501'; END IF;
          IF p_limit IS NULL OR p_limit<1 OR p_limit>100
             OR (p_state IS NOT NULL AND p_state NOT IN ('pending_checkout','active','past_due','grace_period','suspended','canceling','canceled','none'))
             OR (p_source IS NOT NULL AND p_source NOT IN ('stripe','simulated','catalog_only','none')) THEN
            RAISE EXCEPTION 'platform_billing_invalid_filter' USING ERRCODE='22023';
          END IF;
          WITH rows AS (
            SELECT o.id,o.name,o.status AS organization_status,
              coalesce(s.plan_code,c.plan_code) AS plan_code,coalesce(s.version_number,c.version_number) AS version_number,
              coalesce(s.currency,c.currency) AS currency,s.subscription_state,c.contract_state,
              coalesce(s.provider,CASE WHEN c.contract_state IS NULL THEN 'none' ELSE 'catalog_only' END) AS source,
              s.current_period_end,coalesce(s.cancel_at_period_end,false) AS cancel_at_period_end,
              CASE WHEN EXISTS(
                SELECT 1 FROM public.billing_reconciliation_differences d
                WHERE d.organization_id=o.id AND d.resolved_at IS NULL AND d.difference_code<>'in_sync'
              ) THEN 'needs_review' ELSE 'not_checked' END AS reconciliation_status
            FROM public.organizations o
            LEFT JOIN LATERAL (
              SELECT s.provider,s.currency,s.state AS subscription_state,s.current_period_end,s.cancel_at_period_end,
                     p.code AS plan_code,v.version_number
              FROM public.subscriptions s
              JOIN public.plan_versions v ON v.id=s.plan_version_id
              JOIN public.plan_catalog p ON p.id=v.plan_id
              WHERE s.organization_id=o.id AND s.state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling')
              ORDER BY s.updated_at DESC,s.id DESC LIMIT 1
            ) s ON true
            LEFT JOIN LATERAL (
              SELECT c.state AS contract_state,c.currency,p.code AS plan_code,v.version_number
              FROM public.organization_plan_contracts c
              JOIN public.plan_versions v ON v.id=c.plan_version_id
              JOIN public.plan_catalog p ON p.id=v.plan_id
              WHERE c.organization_id=o.id AND c.state IN ('pending','active','suspended')
              ORDER BY c.updated_at DESC,c.id DESC LIMIT 1
            ) c ON true
            WHERE (p_after IS NULL OR o.id>p_after)
          ), filtered AS (
            SELECT * FROM rows
            WHERE (p_state IS NULL OR coalesce(subscription_state,contract_state,'none')=p_state)
              AND (p_source IS NULL OR source=p_source)
            ORDER BY id LIMIT p_limit+1
          ), page AS (SELECT * FROM filtered LIMIT p_limit)
          SELECT jsonb_build_object(
            'items',coalesce(jsonb_agg(jsonb_build_object(
              'id',id,'name',name,'organization_status',organization_status,'plan_code',plan_code,
              'version_number',version_number,'currency',currency,'subscription_state',subscription_state,
              'contract_state',contract_state,'source',source,'current_period_end',current_period_end,
              'cancel_at_period_end',cancel_at_period_end,'reconciliation_status',reconciliation_status
            ) ORDER BY id),'[]'::jsonb),
            'next_cursor',(SELECT id::text FROM filtered ORDER BY id OFFSET p_limit LIMIT 1)
          ) INTO v_payload FROM page;
          RETURN v_payload;
        END $fn$
    """)
    op.execute(r"""
        CREATE FUNCTION app_private.get_platform_billing_organization(p_organization_id uuid)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_organization jsonb;
        BEGIN
          IF v_actor IS NULL OR NOT EXISTS(
            SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin'
          ) THEN RAISE EXCEPTION 'platform_billing_forbidden' USING ERRCODE='42501'; END IF;
          IF p_organization_id IS NULL THEN RETURN NULL; END IF;
          SELECT item INTO v_organization FROM (
            SELECT jsonb_build_object(
              'id',o.id,'name',o.name,'organization_status',o.status,
              'plan_code',coalesce(s.plan_code,c.plan_code),'version_number',coalesce(s.version_number,c.version_number),
              'currency',coalesce(s.currency,c.currency),'subscription_state',s.subscription_state,
              'contract_state',c.contract_state,
              'source',coalesce(s.provider,CASE WHEN c.contract_state IS NULL THEN 'none' ELSE 'catalog_only' END),
              'current_period_end',s.current_period_end,'cancel_at_period_end',coalesce(s.cancel_at_period_end,false),
              'reconciliation_status',CASE WHEN EXISTS(
                SELECT 1 FROM public.billing_reconciliation_differences d WHERE d.organization_id=o.id
                  AND d.resolved_at IS NULL AND d.difference_code<>'in_sync'
              ) THEN 'needs_review' ELSE 'not_checked' END
            ) AS item
            FROM public.organizations o
            LEFT JOIN LATERAL (
              SELECT s.provider,s.currency,s.state AS subscription_state,s.current_period_end,s.cancel_at_period_end,
                p.code AS plan_code,v.version_number FROM public.subscriptions s
              JOIN public.plan_versions v ON v.id=s.plan_version_id JOIN public.plan_catalog p ON p.id=v.plan_id
              WHERE s.organization_id=o.id AND s.state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling')
              ORDER BY s.updated_at DESC,s.id DESC LIMIT 1
            ) s ON true
            LEFT JOIN LATERAL (
              SELECT c.state AS contract_state,c.currency,p.code AS plan_code,v.version_number FROM public.organization_plan_contracts c
              JOIN public.plan_versions v ON v.id=c.plan_version_id JOIN public.plan_catalog p ON p.id=v.plan_id
              WHERE c.organization_id=o.id AND c.state IN ('pending','active','suspended') ORDER BY c.updated_at DESC,c.id DESC LIMIT 1
            ) c ON true WHERE o.id=p_organization_id
          ) detail;
          IF v_organization IS NULL THEN RETURN NULL; END IF;
          RETURN jsonb_build_object(
            'organization',v_organization,
            'events',coalesce((SELECT jsonb_agg(jsonb_build_object('event_type',event_type,'occurred_at',occurred_at) ORDER BY occurred_at DESC)
              FROM (SELECT event_type,occurred_at FROM public.billing_events WHERE organization_id=p_organization_id
                    ORDER BY occurred_at DESC,id DESC LIMIT 20) events),'[]'::jsonb),
            'interventions',coalesce((SELECT jsonb_agg(jsonb_build_object(
                'kind',command_kind,'status',status,'created_at',created_at,'updated_at',updated_at) ORDER BY created_at DESC)
              FROM (SELECT command_kind,status,created_at,updated_at FROM public.billing_commands WHERE organization_id=p_organization_id
                    ORDER BY created_at DESC,id DESC LIMIT 20) commands),'[]'::jsonb)
          );
        END $fn$
    """)
    for signature in _FUNCTIONS:
        op.execute(f"ALTER FUNCTION {signature} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC, prospect_worker")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")


def downgrade() -> None:
    for signature in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {signature}")
