"""Restore Meta usage codes on databases that had already applied revision 0026.

Revision ID: 20260929_0029
Revises: 20260929_0028
"""

from alembic import op

revision = "20260929_0029"
down_revision = "20260929_0028"
branch_labels = None
depends_on = None

_META_CODES = (
    "'google.places_text_search.quota','google.places_text_search.request',"
    "'google.places_autocomplete.request','google.places_details.request','google.maps_static.request',"
    "'platform.csv_export','platform.csv_import',"
    "'meta_lead_ads.webhook_accepted','meta_lead_ads.fetch_attempted','meta_lead_ads.imported',"
    "'meta_lead_ads.quarantined','meta_lead_ads.failed'"
)
_META_OUTCOMES = "'accepted','rejected','attempted','succeeded','failed','indeterminate','expired','quarantined'"
_LEGACY_CODES = (
    "'google.places_text_search.quota','google.places_text_search.request',"
    "'google.places_autocomplete.request','google.places_details.request','google.maps_static.request',"
    "'platform.csv_export','platform.csv_import'"
)
_LEGACY_OUTCOMES = "'accepted','rejected','attempted','succeeded','failed','indeterminate','expired'"
_FUNCTION_SIGNATURE = (
    "app_private.record_usage_event(uuid,uuid,text,text,text,timestamptz,bigint,text,integer,integer,integer,"
    "timestamptz,bigint,bigint,bigint,bigint,bigint,bigint,bigint)"
)


def _record_usage_function_sql(codes: str, outcomes: str) -> str:
    return f"""
        CREATE OR REPLACE FUNCTION app_private.record_usage_event(
            p_membership uuid, p_operation uuid, p_code text, p_kind text, p_outcome text,
            p_occurred timestamptz, p_units bigint, p_policy text, p_user_limit integer,
            p_organization_limit integer, p_warning integer, p_reset_at timestamptz,
            p_rows bigint, p_created bigint, p_duplicates bigint, p_review bigint,
            p_quarantined bigint, p_omitted bigint, p_bytes bigint
        ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, app_private AS $$
        DECLARE
            v_org uuid := app_private.current_organization_id();
            v_actor uuid := nullif(current_setting('app.actor_id', true), '')::uuid;
            v_inserted uuid;
            v_user uuid;
        BEGIN
            PERFORM pg_advisory_xact_lock(hashtextextended(p_operation::text, 0));
            IF p_code NOT IN ({codes})
               OR p_kind NOT IN ('quota_reserved','quota_rejected','upstream_attempted','upstream_succeeded',
                'upstream_failed','export_requested','export_ready','export_failed','export_expired','import_confirmed')
               OR p_outcome NOT IN ({outcomes})
               OR p_units < 0 OR p_occurred IS NULL OR v_actor IS NULL THEN
                RAISE EXCEPTION 'invalid_usage_event';
            END IF;
            SELECT user_id INTO v_user FROM public.memberships
             WHERE id = p_membership AND organization_id = v_org AND user_id = v_actor;
            IF v_user IS NULL THEN RAISE EXCEPTION 'invalid_usage_actor'; END IF;

            INSERT INTO public.usage_operation_events (
                id, organization_id, actor_user_id, actor_membership_id, operation_id, usage_code,
                event_kind, outcome, occurred_at, unit_count, policy_code, user_limit,
                organization_limit, warning_threshold_percent, reset_at, row_count, created_count,
                duplicate_count, review_count, quarantined_count, omitted_count, byte_count, schema_version
            ) VALUES (
                gen_random_uuid(), v_org, v_user, p_membership, p_operation, p_code,
                p_kind, p_outcome, p_occurred, p_units, p_policy, p_user_limit,
                p_organization_limit, p_warning, p_reset_at, p_rows, p_created,
                p_duplicates, p_review, p_quarantined, p_omitted, p_bytes, 1
            ) ON CONFLICT (organization_id, operation_id, event_kind) DO NOTHING RETURNING id INTO v_inserted;
            IF v_inserted IS NULL THEN RETURN false; END IF;

            INSERT INTO public.usage_daily_counters (
                id, organization_id, actor_user_id, usage_day, usage_code, event_kind, outcome,
                unit_count, row_count, created_count, duplicate_count, review_count,
                quarantined_count, omitted_count, byte_count, last_recorded_at
            )
            SELECT gen_random_uuid(), v_org, scope_user, (p_occurred AT TIME ZONE 'UTC')::date,
                p_code, p_kind, p_outcome, p_units, coalesce(p_rows, 0), coalesce(p_created, 0),
                coalesce(p_duplicates, 0), coalesce(p_review, 0), coalesce(p_quarantined, 0),
                coalesce(p_omitted, 0), coalesce(p_bytes, 0), p_occurred
            FROM (VALUES (v_user), (NULL::uuid)) AS scopes(scope_user)
            ON CONFLICT ON CONSTRAINT uq_usage_daily_dimensions DO UPDATE SET
                unit_count = usage_daily_counters.unit_count + excluded.unit_count,
                row_count = usage_daily_counters.row_count + excluded.row_count,
                created_count = usage_daily_counters.created_count + excluded.created_count,
                duplicate_count = usage_daily_counters.duplicate_count + excluded.duplicate_count,
                review_count = usage_daily_counters.review_count + excluded.review_count,
                quarantined_count = usage_daily_counters.quarantined_count + excluded.quarantined_count,
                omitted_count = usage_daily_counters.omitted_count + excluded.omitted_count,
                byte_count = usage_daily_counters.byte_count + excluded.byte_count,
                last_recorded_at = greatest(usage_daily_counters.last_recorded_at, excluded.last_recorded_at);
            RETURN true;
        END $$
    """


def _replace_catalog(codes: str, outcomes: str) -> None:
    op.drop_constraint("usage_events_code_allowed", "usage_operation_events", type_="check")
    op.drop_constraint("usage_events_outcome_allowed", "usage_operation_events", type_="check")
    op.create_check_constraint("usage_events_code_allowed", "usage_operation_events", f"usage_code IN ({codes})")
    op.create_check_constraint("usage_events_outcome_allowed", "usage_operation_events", f"outcome IN ({outcomes})")

    op.drop_constraint("usage_daily_code_allowed", "usage_daily_counters", type_="check")
    op.drop_constraint("usage_daily_outcome_allowed", "usage_daily_counters", type_="check")
    op.create_check_constraint("usage_daily_code_allowed", "usage_daily_counters", f"usage_code IN ({codes})")
    op.create_check_constraint("usage_daily_outcome_allowed", "usage_daily_counters", f"outcome IN ({outcomes})")

    op.execute(_record_usage_function_sql(codes, outcomes))
    op.execute(f"ALTER FUNCTION {_FUNCTION_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_FUNCTION_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_FUNCTION_SIGNATURE} TO prospect_app, prospect_worker")


def upgrade() -> None:
    _replace_catalog(_META_CODES, _META_OUTCOMES)


def downgrade() -> None:
    _replace_catalog(_LEGACY_CODES, _LEGACY_OUTCOMES)
