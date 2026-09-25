"""Phase 4.4 durable usage registry and reports.

Revision ID: 20260924_0024
Revises: 20260924_0023
"""

import sqlalchemy as sa
from alembic import op

revision = "20260924_0024"
down_revision = "20260924_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_organizations_google_search_daily_limit_positive"), "organizations", type_="check")
    op.alter_column("organizations", "google_search_daily_limit", new_column_name="google_search_daily_limit_legacy")
    op.create_check_constraint(
        "google_search_daily_limit_legacy_positive",
        "organizations",
        "google_search_daily_limit_legacy > 0",
    )

    op.create_table(
        "usage_operation_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "actor_membership_id", sa.Uuid(), sa.ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("usage_code", sa.String(64), nullable=False),
        sa.Column("event_kind", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unit_count", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("policy_code", sa.String(64), nullable=True),
        sa.Column("user_limit", sa.Integer(), nullable=True),
        sa.Column("organization_limit", sa.Integer(), nullable=True),
        sa.Column("warning_threshold_percent", sa.Integer(), nullable=True),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("created_count", sa.BigInteger(), nullable=True),
        sa.Column("duplicate_count", sa.BigInteger(), nullable=True),
        sa.Column("review_count", sa.BigInteger(), nullable=True),
        sa.Column("quarantined_count", sa.BigInteger(), nullable=True),
        sa.Column("omitted_count", sa.BigInteger(), nullable=True),
        sa.Column("byte_count", sa.BigInteger(), nullable=True),
        sa.Column("schema_version", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "operation_id", "event_kind", name="uq_usage_events_operation_kind"),
        sa.CheckConstraint(
            "usage_code IN ('google.places_text_search.quota','google.places_text_search.request',"
            "'google.places_autocomplete.request','google.places_details.request','google.maps_static.request',"
            "'platform.csv_export','platform.csv_import')",
            name="usage_events_code_allowed",
        ),
        sa.CheckConstraint(
            "event_kind IN ('quota_reserved','quota_rejected','upstream_attempted','upstream_succeeded',"
            "'upstream_failed','export_requested','export_ready','export_failed','export_expired','import_confirmed')",
            name="usage_events_kind_allowed",
        ),
        sa.CheckConstraint(
            "outcome IN ('accepted','rejected','attempted','succeeded','failed','indeterminate','expired')",
            name="usage_events_outcome_allowed",
        ),
        sa.CheckConstraint("unit_count >= 0", name="usage_events_units_nonnegative"),
        sa.CheckConstraint(
            "coalesce(row_count,0) >= 0 AND coalesce(created_count,0) >= 0 "
            "AND coalesce(duplicate_count,0) >= 0 AND coalesce(review_count,0) >= 0 "
            "AND coalesce(quarantined_count,0) >= 0 AND coalesce(omitted_count,0) >= 0 "
            "AND coalesce(byte_count,0) >= 0",
            name="usage_events_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "(user_limit IS NULL OR user_limit > 0) AND "
            "(organization_limit IS NULL OR organization_limit > 0) AND "
            "(warning_threshold_percent IS NULL OR warning_threshold_percent BETWEEN 1 AND 100)",
            name="usage_events_policy_values_valid",
        ),
        sa.CheckConstraint("schema_version = 1", name="usage_events_schema_version"),
    )
    op.create_index("ix_usage_events_org_occurred", "usage_operation_events", ["organization_id", "occurred_at"])
    op.create_index(
        "ix_usage_events_org_user_occurred",
        "usage_operation_events",
        ["organization_id", "actor_user_id", "occurred_at"],
    )
    op.create_index(
        "uq_usage_events_terminal",
        "usage_operation_events",
        ["organization_id", "operation_id"],
        unique=True,
        postgresql_where=sa.text("event_kind IN ('upstream_succeeded','upstream_failed')"),
    )

    op.create_table(
        "usage_daily_counters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("usage_day", sa.Date(), nullable=False),
        sa.Column("usage_code", sa.String(64), nullable=False),
        sa.Column("event_kind", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("unit_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("row_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("review_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("quarantined_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("omitted_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("byte_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "actor_user_id",
            "usage_day",
            "usage_code",
            "event_kind",
            "outcome",
            name="uq_usage_daily_dimensions",
            postgresql_nulls_not_distinct=True,
        ),
        sa.CheckConstraint("unit_count >= 0", name="usage_daily_units_nonnegative"),
        sa.CheckConstraint(
            "usage_code IN ('google.places_text_search.quota','google.places_text_search.request',"
            "'google.places_autocomplete.request','google.places_details.request','google.maps_static.request',"
            "'platform.csv_export','platform.csv_import')",
            name="usage_daily_code_allowed",
        ),
        sa.CheckConstraint(
            "event_kind IN ('quota_reserved','quota_rejected','upstream_attempted','upstream_succeeded',"
            "'upstream_failed','export_requested','export_ready','export_failed','export_expired','import_confirmed')",
            name="usage_daily_kind_allowed",
        ),
        sa.CheckConstraint(
            "outcome IN ('accepted','rejected','attempted','succeeded','failed','indeterminate','expired')",
            name="usage_daily_outcome_allowed",
        ),
        sa.CheckConstraint(
            "row_count >= 0 AND created_count >= 0 AND duplicate_count >= 0 AND review_count >= 0 "
            "AND quarantined_count >= 0 AND omitted_count >= 0 AND byte_count >= 0",
            name="usage_daily_counts_nonnegative",
        ),
    )
    op.create_index("ix_usage_daily_org_day", "usage_daily_counters", ["organization_id", "usage_day"])
    op.create_index(
        "ix_usage_daily_org_user_day", "usage_daily_counters", ["organization_id", "actor_user_id", "usage_day"]
    )

    for table in ("usage_operation_events", "usage_daily_counters"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON public.{table} FOR SELECT TO prospect_app
            USING (organization_id = app_private.current_organization_id())
        """)
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC")
        op.execute(f"GRANT SELECT ON public.{table} TO prospect_app")
        if table == "usage_operation_events":
            op.execute(f"""
                CREATE POLICY {table}_writer ON public.{table} FOR ALL TO prospect_rls_definer
                USING (organization_id = app_private.current_organization_id())
                WITH CHECK (organization_id = app_private.current_organization_id())
            """)
            op.execute(f"GRANT SELECT, INSERT ON public.{table} TO prospect_rls_definer")
        else:
            op.execute(f"""
                CREATE POLICY {table}_writer ON public.{table} FOR ALL TO prospect_rls_definer
                USING (organization_id = app_private.current_organization_id())
                WITH CHECK (organization_id = app_private.current_organization_id())
            """)
            op.execute(f"GRANT SELECT, INSERT, UPDATE ON public.{table} TO prospect_rls_definer")
    for table in ("export_artifacts", "csv_import_sessions"):
        op.execute(f"""
            CREATE POLICY {table}_usage_writer ON public.{table} FOR SELECT TO prospect_rls_definer
            USING (organization_id = app_private.current_organization_id())
        """)
        op.execute(f"GRANT SELECT ON public.{table} TO prospect_rls_definer")

    op.execute("""
        CREATE FUNCTION app_private.record_usage_event(
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
            IF p_code NOT IN ('google.places_text_search.quota','google.places_text_search.request',
                'google.places_autocomplete.request','google.places_details.request','google.maps_static.request',
                'platform.csv_export','platform.csv_import')
               OR p_kind NOT IN ('quota_reserved','quota_rejected','upstream_attempted','upstream_succeeded',
                'upstream_failed','export_requested','export_ready','export_failed','export_expired','import_confirmed')
               OR p_outcome NOT IN ('accepted','rejected','attempted','succeeded','failed','indeterminate','expired')
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
    """)
    op.execute(
        "ALTER FUNCTION app_private.record_usage_event(uuid,uuid,text,text,text,timestamptz,bigint,text,integer,integer,integer,timestamptz,bigint,bigint,bigint,bigint,bigint,bigint,bigint) OWNER TO prospect_rls_definer"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app_private.record_usage_event(uuid,uuid,text,text,text,timestamptz,bigint,text,integer,integer,integer,timestamptz,bigint,bigint,bigint,bigint,bigint,bigint,bigint) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_private.record_usage_event(uuid,uuid,text,text,text,timestamptz,bigint,text,integer,integer,integer,timestamptz,bigint,bigint,bigint,bigint,bigint,bigint,bigint) TO prospect_app, prospect_worker"
    )
    op.execute("GRANT SELECT ON public.memberships TO prospect_rls_definer")

    op.execute("""
        CREATE FUNCTION app_private.capture_export_usage() RETURNS trigger LANGUAGE plpgsql
        SECURITY DEFINER SET search_path = pg_catalog, public, app_private AS $$
        DECLARE v_artifact record; v_kind text; v_outcome text;
        BEGIN
          IF TG_OP = 'INSERT' THEN v_kind := 'export_requested'; v_outcome := 'accepted';
          ELSIF NEW.status IS NOT DISTINCT FROM OLD.status THEN RETURN NEW;
          ELSIF NEW.status = 'ready' THEN v_kind := 'export_ready'; v_outcome := 'succeeded';
          ELSIF NEW.status = 'failed' THEN v_kind := 'export_failed'; v_outcome := 'failed';
          ELSIF NEW.status = 'expired' THEN v_kind := 'export_expired'; v_outcome := 'expired';
          ELSE RETURN NEW; END IF;
          SELECT row_count, omitted_count, byte_size INTO v_artifact FROM public.export_artifacts WHERE export_id = NEW.id;
          PERFORM app_private.record_usage_event(NEW.requester_membership_id, NEW.id, 'platform.csv_export',
            v_kind, v_outcome, coalesce(NEW.finished_at, NEW.created_at, clock_timestamp()), 1,
            'export_limits_v1', NULL, NULL, NULL, NULL, v_artifact.row_count, NULL, NULL, NULL, NULL,
            v_artifact.omitted_count, v_artifact.byte_size);
          RETURN NEW;
        END $$
    """)
    op.execute("ALTER FUNCTION app_private.capture_export_usage() OWNER TO prospect_rls_definer")
    op.execute(
        "CREATE TRIGGER capture_export_usage AFTER INSERT OR UPDATE OF status ON public.export_requests FOR EACH ROW EXECUTE FUNCTION app_private.capture_export_usage()"
    )

    op.execute("""
        CREATE FUNCTION app_private.capture_import_usage() RETURNS trigger LANGUAGE plpgsql
        SECURITY DEFINER SET search_path = pg_catalog, public, app_private AS $$
        DECLARE v_membership uuid; v_rows bigint;
        BEGIN
          SELECT id INTO v_membership FROM public.memberships
           WHERE organization_id = NEW.organization_id
             AND user_id = nullif(current_setting('app.actor_id', true), '')::uuid
           ORDER BY created_at, id LIMIT 1;
          SELECT row_count INTO v_rows FROM public.csv_import_sessions WHERE id = NEW.session_id;
          PERFORM app_private.record_usage_event(v_membership, NEW.id, 'platform.csv_import',
            'import_confirmed', 'succeeded', NEW.completed_at, 1, 'import_limits_v1',
            NULL, NULL, NULL, NULL, v_rows, NEW.created_count, NEW.duplicate_count,
            NEW.review_count, NEW.quarantined_count, NULL, NULL);
          RETURN NEW;
        END $$
    """)
    op.execute("ALTER FUNCTION app_private.capture_import_usage() OWNER TO prospect_rls_definer")
    op.execute(
        "CREATE TRIGGER capture_import_usage AFTER INSERT ON public.csv_import_runs FOR EACH ROW EXECUTE FUNCTION app_private.capture_import_usage()"
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.usage_operation_events TO prospect_job_claim_owner")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.usage_daily_counters TO prospect_job_claim_owner")
    op.execute("""
        CREATE POLICY usage_operation_events_maintenance ON public.usage_operation_events
        FOR ALL TO prospect_job_claim_owner USING (true) WITH CHECK (true)
    """)
    op.execute("""
        CREATE POLICY usage_daily_counters_maintenance ON public.usage_daily_counters
        FOR ALL TO prospect_job_claim_owner USING (true) WITH CHECK (true)
    """)
    op.execute("""
        CREATE FUNCTION app_private.reconcile_usage_events(p_batch integer) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, app_private AS $$
        DECLARE v_attempt record; v_inserted uuid; v_count integer := 0;
        BEGIN
          IF p_batch < 1 OR p_batch > 1000 THEN RAISE EXCEPTION 'invalid_usage_reconcile_batch'; END IF;
          FOR v_attempt IN
            SELECT e.* FROM public.usage_operation_events e
             WHERE e.event_kind = 'upstream_attempted'
               AND e.occurred_at < clock_timestamp() - interval '30 minutes'
               AND NOT EXISTS (
                 SELECT 1 FROM public.usage_operation_events terminal
                  WHERE terminal.organization_id = e.organization_id
                    AND terminal.operation_id = e.operation_id
                    AND terminal.event_kind IN ('upstream_succeeded','upstream_failed')
               )
             ORDER BY e.occurred_at, e.id LIMIT p_batch FOR UPDATE SKIP LOCKED
          LOOP
            PERFORM pg_advisory_xact_lock(hashtextextended(v_attempt.operation_id::text, 0));
            IF EXISTS (
              SELECT 1 FROM public.usage_operation_events terminal
               WHERE terminal.organization_id = v_attempt.organization_id
                 AND terminal.operation_id = v_attempt.operation_id
                 AND terminal.event_kind IN ('upstream_succeeded','upstream_failed')
            ) THEN CONTINUE; END IF;
            INSERT INTO public.usage_operation_events (
              id, organization_id, actor_user_id, actor_membership_id, operation_id, usage_code,
              event_kind, outcome, occurred_at, unit_count, policy_code, user_limit,
              organization_limit, warning_threshold_percent, reset_at, schema_version
            ) VALUES (
              gen_random_uuid(), v_attempt.organization_id, v_attempt.actor_user_id,
              v_attempt.actor_membership_id, v_attempt.operation_id, v_attempt.usage_code,
              'upstream_failed', 'indeterminate', clock_timestamp(), v_attempt.unit_count,
              v_attempt.policy_code, v_attempt.user_limit, v_attempt.organization_limit,
              v_attempt.warning_threshold_percent, v_attempt.reset_at, 1
            ) ON CONFLICT DO NOTHING RETURNING id INTO v_inserted;
            IF v_inserted IS NULL THEN CONTINUE; END IF;
            INSERT INTO public.usage_daily_counters (
              id, organization_id, actor_user_id, usage_day, usage_code, event_kind, outcome,
              unit_count, row_count, created_count, duplicate_count, review_count,
              quarantined_count, omitted_count, byte_count, last_recorded_at
            )
            SELECT gen_random_uuid(), v_attempt.organization_id, scope_user,
              (v_attempt.occurred_at AT TIME ZONE 'UTC')::date, v_attempt.usage_code,
              'upstream_failed', 'indeterminate', v_attempt.unit_count, 0, 0, 0, 0, 0, 0, 0,
              clock_timestamp()
            FROM (VALUES (v_attempt.actor_user_id), (NULL::uuid)) AS scopes(scope_user)
            ON CONFLICT ON CONSTRAINT uq_usage_daily_dimensions DO UPDATE SET
              unit_count = usage_daily_counters.unit_count + excluded.unit_count,
              last_recorded_at = greatest(usage_daily_counters.last_recorded_at, excluded.last_recorded_at);
            v_count := v_count + 1;
          END LOOP;
          RETURN v_count;
        END $$
    """)
    op.execute("ALTER FUNCTION app_private.reconcile_usage_events(integer) OWNER TO prospect_job_claim_owner")
    op.execute("REVOKE ALL ON FUNCTION app_private.reconcile_usage_events(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.reconcile_usage_events(integer) TO prospect_worker")

    op.execute("""
        CREATE FUNCTION app_private.purge_usage_data(p_batch integer) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        DECLARE v_events integer; v_counters integer;
        BEGIN
          IF p_batch < 1 OR p_batch > 1000 THEN RAISE EXCEPTION 'invalid_usage_purge_batch'; END IF;
          WITH due AS (
            SELECT id FROM public.usage_operation_events
             WHERE occurred_at < clock_timestamp() - interval '90 days'
             ORDER BY occurred_at, id LIMIT p_batch FOR UPDATE SKIP LOCKED
          ) DELETE FROM public.usage_operation_events WHERE id IN (SELECT id FROM due);
          GET DIAGNOSTICS v_events = ROW_COUNT;
          WITH due AS (
            SELECT id FROM public.usage_daily_counters
             WHERE usage_day < (clock_timestamp() AT TIME ZONE 'UTC')::date - 400
             ORDER BY usage_day, id LIMIT p_batch FOR UPDATE SKIP LOCKED
          ) DELETE FROM public.usage_daily_counters WHERE id IN (SELECT id FROM due);
          GET DIAGNOSTICS v_counters = ROW_COUNT;
          RETURN jsonb_build_object('events', v_events, 'counters', v_counters);
        END $$
    """)
    op.execute("ALTER FUNCTION app_private.purge_usage_data(integer) OWNER TO prospect_job_claim_owner")
    op.execute("REVOKE ALL ON FUNCTION app_private.purge_usage_data(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.purge_usage_data(integer) TO prospect_worker")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_private.purge_usage_data(integer)")
    op.execute("DROP FUNCTION IF EXISTS app_private.reconcile_usage_events(integer)")
    op.execute("DROP TRIGGER IF EXISTS capture_import_usage ON public.csv_import_runs")
    op.execute("DROP FUNCTION IF EXISTS app_private.capture_import_usage()")
    op.execute("DROP TRIGGER IF EXISTS capture_export_usage ON public.export_requests")
    op.execute("DROP FUNCTION IF EXISTS app_private.capture_export_usage()")
    op.execute(
        "DROP FUNCTION IF EXISTS app_private.record_usage_event(uuid,uuid,text,text,text,timestamptz,bigint,text,integer,integer,integer,timestamptz,bigint,bigint,bigint,bigint,bigint,bigint,bigint)"
    )
    op.execute("DROP POLICY IF EXISTS export_artifacts_usage_writer ON public.export_artifacts")
    op.execute("DROP POLICY IF EXISTS csv_import_sessions_usage_writer ON public.csv_import_sessions")
    op.drop_table("usage_daily_counters")
    op.drop_table("usage_operation_events")
    op.drop_constraint(
        op.f("ck_organizations_google_search_daily_limit_legacy_positive"), "organizations", type_="check"
    )
    op.alter_column("organizations", "google_search_daily_limit_legacy", new_column_name="google_search_daily_limit")
    op.create_check_constraint("google_search_daily_limit_positive", "organizations", "google_search_daily_limit > 0")
