"""Ajouter la file PostgreSQL durable de la phase 4.2.

Revision ID: 20260923_0022
Revises: 20260922_0021
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0022"
down_revision: str | None = "20260922_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("jobs", "job_scheduler_state", "job_attempts", "job_events")


def upgrade() -> None:
    op.execute("""
        DO $check$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prospect_worker'
                         AND rolcanlogin AND NOT rolinherit AND NOT rolbypassrls
                         AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole) THEN
            RAISE EXCEPTION 'Le rôle prospect_worker doit être provisionné avant la migration 20260923_0022.';
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prospect_job_claim_owner'
                         AND NOT rolcanlogin AND NOT rolbypassrls AND NOT rolsuper
                         AND NOT rolcreatedb AND NOT rolcreaterole) THEN
            RAISE EXCEPTION 'Le rôle prospect_job_claim_owner doit être provisionné.';
          END IF;
        END $check$;
    """)
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("replay_of_job_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("actor_membership_id", sa.Uuid(), nullable=True),
        sa.Column("system_origin", sa.String(64), nullable=True),
        sa.Column("idempotency_key_digest", sa.String(64), nullable=False),
        sa.Column("idempotency_key_version", sa.Integer(), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_token", sa.Uuid(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("result_code", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("organization_id", "id", name="uq_jobs_organization_id"),
        sa.UniqueConstraint("organization_id", "type", "idempotency_key_digest", name="uq_jobs_idempotency"),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')", name="ck_jobs_status_allowed"
        ),
        sa.CheckConstraint(
            "attempt_count BETWEEN 0 AND max_attempts AND max_attempts BETWEEN 1 AND 3", name="ck_jobs_attempts_allowed"
        ),
        sa.CheckConstraint("schema_version > 0 AND version > 0", name="ck_jobs_versions_positive"),
        sa.CheckConstraint("(actor_membership_id IS NULL) <> (system_origin IS NULL)", name="ck_jobs_origin_exclusive"),
    )
    op.create_index("ix_jobs_claim", "jobs", ["status", "available_at", "created_at"])
    op.create_index("ix_jobs_organization_status", "jobs", ["organization_id", "status"])
    op.create_index("ix_jobs_expiry", "jobs", ["expires_at"])
    op.create_table(
        "job_scheduler_state",
        sa.Column(
            "organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("queued_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "queued_count >= 0 AND active_count BETWEEN 0 AND 1", name="ck_job_scheduler_state_counts_allowed"
        ),
    )
    op.create_table(
        "job_attempts",
        sa.Column("job_id", sa.Uuid(), primary_key=True),
        sa.Column("attempt_number", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("owner_token", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_code", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["organization_id", "job_id"], ["jobs.organization_id", "jobs.id"], ondelete="CASCADE"),
        sa.CheckConstraint("attempt_number > 0", name="ck_job_attempts_number_positive"),
    )
    op.create_table(
        "job_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("old_status", sa.String(16), nullable=True),
        sa.Column("new_status", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id", "job_id"], ["jobs.organization_id", "jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_job_events_job_created", "job_events", ["job_id", "created_at"])
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(128), primary_key=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_cleanup_at", sa.DateTime(timezone=True), nullable=True),
    )

    for table_name in _TABLES:
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table_name}_tenant ON public.{table_name} FOR ALL TO prospect_app, prospect_worker
            USING (organization_id = app_private.current_organization_id())
            WITH CHECK (organization_id = app_private.current_organization_id())
        """)
        op.execute(f"""
            CREATE POLICY {table_name}_claim_owner ON public.{table_name} FOR ALL TO prospect_job_claim_owner
            USING (true) WITH CHECK (true)
        """)
        op.execute(f"REVOKE ALL ON TABLE public.{table_name} FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA public TO prospect_worker")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.current_organization_id() TO prospect_worker")
    op.execute("GRANT SELECT ON public.organizations, public.memberships TO prospect_worker")
    op.execute("GRANT SELECT (id, status) ON public.users TO prospect_worker")
    op.execute("""
        CREATE POLICY organizations_worker_tenant ON public.organizations FOR SELECT TO prospect_worker
        USING (id = app_private.current_organization_id())
    """)
    op.execute("""
        CREATE POLICY memberships_worker_tenant ON public.memberships FOR SELECT TO prospect_worker
        USING (organization_id = app_private.current_organization_id())
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.jobs, public.job_scheduler_state TO prospect_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.jobs, public.job_scheduler_state TO prospect_worker")
    op.execute("GRANT SELECT, INSERT ON public.job_events TO prospect_app")
    op.execute("GRANT SELECT, INSERT ON public.job_events TO prospect_worker")
    op.execute("GRANT SELECT ON public.job_attempts TO prospect_app")
    op.execute("GRANT SELECT, UPDATE ON public.job_attempts TO prospect_worker")
    op.execute("REVOKE ALL ON public.worker_heartbeats FROM PUBLIC")
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.worker_heartbeats TO prospect_worker")
    op.execute("GRANT SELECT, DELETE ON public.worker_heartbeats TO prospect_job_claim_owner")
    op.execute("GRANT USAGE ON SCHEMA public TO prospect_job_claim_owner")
    op.execute("GRANT SELECT, UPDATE, DELETE ON public.jobs TO prospect_job_claim_owner")
    op.execute("GRANT SELECT, UPDATE ON public.job_scheduler_state TO prospect_job_claim_owner")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.job_attempts TO prospect_job_claim_owner")
    op.execute("GRANT SELECT, INSERT, DELETE ON public.job_events TO prospect_job_claim_owner")
    op.execute("GRANT USAGE, CREATE ON SCHEMA app_private TO prospect_job_claim_owner")
    op.execute("GRANT USAGE ON SCHEMA app_private TO prospect_worker")

    op.execute("""
        CREATE FUNCTION app_private.claim_job(p_supported text[]) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_org uuid; v_job public.jobs%ROWTYPE; v_token uuid := gen_random_uuid(); v_now timestamptz := clock_timestamp();
        BEGIN
          SELECT s.organization_id INTO v_org FROM public.job_scheduler_state s
          WHERE EXISTS (
            SELECT 1 FROM public.jobs j WHERE j.organization_id = s.organization_id
              AND (j.type || ':' || j.schema_version::text) = ANY(p_supported)
              AND ((j.status = 'queued' AND j.available_at <= v_now AND s.active_count = 0)
                   OR (j.status = 'running' AND j.lease_until <= v_now))
          )
          ORDER BY s.last_claimed_at NULLS FIRST, s.organization_id
          LIMIT 1 FOR UPDATE OF s SKIP LOCKED;
          IF v_org IS NULL THEN RETURN NULL; END IF;
          SELECT * INTO v_job FROM public.jobs j
          WHERE j.organization_id = v_org AND (j.type || ':' || j.schema_version::text) = ANY(p_supported)
            AND ((j.status = 'running' AND j.lease_until <= v_now)
                 OR (j.status = 'queued' AND j.available_at <= v_now
                     AND (SELECT active_count FROM public.job_scheduler_state WHERE organization_id = v_org) = 0))
          ORDER BY CASE WHEN j.status = 'running' THEN 0 ELSE 1 END, j.available_at, j.created_at
          LIMIT 1 FOR UPDATE OF j SKIP LOCKED;
          IF v_job.id IS NULL THEN RETURN NULL; END IF;
          IF v_job.attempt_count >= v_job.max_attempts THEN
            UPDATE public.job_attempts SET finished_at = v_now, result_code = 'lease_lost'
              WHERE job_id = v_job.id AND attempt_number = v_job.attempt_count AND finished_at IS NULL;
            UPDATE public.jobs SET status = 'failed', finished_at = v_now, lease_until = NULL,
              owner_token = NULL, last_error_code = 'attempts_exhausted',
              expires_at = v_now + interval '90 days', version = version + 1 WHERE id = v_job.id;
            UPDATE public.job_scheduler_state SET active_count = 0 WHERE organization_id = v_org;
            INSERT INTO public.job_events (id, job_id, organization_id, old_status, new_status, reason_code, created_at)
              VALUES (gen_random_uuid(), v_job.id, v_org, v_job.status, 'failed', 'attempts_exhausted', v_now);
            RETURN NULL;
          END IF;
          IF v_job.status = 'running' THEN
            UPDATE public.job_attempts SET finished_at = v_now, result_code = 'lease_lost'
            WHERE job_id = v_job.id AND attempt_number = v_job.attempt_count AND finished_at IS NULL;
          ELSE
            UPDATE public.job_scheduler_state SET queued_count = queued_count - 1 WHERE organization_id = v_org;
          END IF;
          UPDATE public.job_scheduler_state
            SET active_count = 1, last_claimed_at = v_now WHERE organization_id = v_org;
          UPDATE public.jobs SET status = 'running', attempt_count = attempt_count + 1,
            owner_token = v_token, lease_until = v_now + interval '90 seconds', heartbeat_at = v_now,
            started_at = COALESCE(started_at, v_now), version = version + 1
            WHERE id = v_job.id;
          INSERT INTO public.job_attempts (job_id, attempt_number, organization_id, owner_token, started_at)
            VALUES (v_job.id, v_job.attempt_count + 1, v_org, v_token, v_now);
          INSERT INTO public.job_events (id, job_id, organization_id, old_status, new_status, reason_code, created_at)
            VALUES (gen_random_uuid(), v_job.id, v_org, v_job.status, 'running', 'claimed', v_now);
          RETURN jsonb_build_object('id', v_job.id, 'organization_id', v_org, 'type', v_job.type,
            'schema_version', v_job.schema_version, 'subject_id', v_job.subject_id,
            'subject_type', v_job.subject_type, 'actor_id', v_job.actor_id,
            'actor_membership_id', v_job.actor_membership_id,
            'system_origin', v_job.system_origin, 'attempt_count', v_job.attempt_count + 1,
            'max_attempts', v_job.max_attempts,
            'owner_token', v_token, 'cancel_requested', v_job.cancel_requested_at IS NOT NULL);
        END $fn$;
    """)
    op.execute("ALTER FUNCTION app_private.claim_job(text[]) OWNER TO prospect_job_claim_owner")
    op.execute("REVOKE ALL ON FUNCTION app_private.claim_job(text[]) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.claim_job(text[]) TO prospect_worker")

    op.execute("""
        CREATE FUNCTION app_private.purge_jobs(p_batch integer) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_count integer;
        BEGIN
          IF p_batch < 1 OR p_batch > 500 THEN RAISE EXCEPTION 'Invalid purge batch'; END IF;
          WITH due AS (SELECT id FROM public.jobs WHERE status IN ('succeeded','failed','cancelled')
                      AND expires_at <= clock_timestamp() ORDER BY expires_at LIMIT p_batch FOR UPDATE SKIP LOCKED)
          DELETE FROM public.jobs WHERE id IN (SELECT id FROM due);
          GET DIAGNOSTICS v_count = ROW_COUNT;
          DELETE FROM public.worker_heartbeats
            WHERE last_seen_at < clock_timestamp() - interval '30 days';
          RETURN v_count;
        END $fn$;
    """)
    op.execute("ALTER FUNCTION app_private.purge_jobs(integer) OWNER TO prospect_job_claim_owner")
    op.execute("REVOKE ALL ON FUNCTION app_private.purge_jobs(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.purge_jobs(integer) TO prospect_worker")

    op.execute("""
        CREATE FUNCTION app_private.job_metrics(p_supported text[]) RETURNS jsonb
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
          SELECT jsonb_build_object(
            'queued', count(*) FILTER (WHERE status = 'queued'),
            'eligible', count(*) FILTER (WHERE status = 'queued' AND available_at <= now()),
            'running', count(*) FILTER (WHERE status = 'running'),
            'failed', count(*) FILTER (WHERE status = 'failed'),
            'unsupported_contracts', count(*) FILTER (WHERE status IN ('queued', 'running')
              AND (type || ':' || schema_version::text) <> ALL(p_supported)),
            'expired_leases', count(*) FILTER (WHERE status = 'running' AND lease_until <= now()),
            'oldest_eligible_seconds', COALESCE(EXTRACT(EPOCH FROM now() -
              min(available_at) FILTER (WHERE status = 'queued' AND available_at <= now())), 0),
            'mean_admission_seconds', COALESCE(avg(EXTRACT(EPOCH FROM started_at - created_at))
              FILTER (WHERE started_at IS NOT NULL), 0),
            'mean_attempt_seconds', COALESCE((SELECT avg(EXTRACT(EPOCH FROM finished_at - started_at))
              FROM public.job_attempts WHERE finished_at IS NOT NULL), 0),
            'attempts_by_code', COALESCE((SELECT jsonb_object_agg(a.result_code, a.total)
              FROM (SELECT result_code, count(*) AS total FROM public.job_attempts
                    WHERE result_code IS NOT NULL GROUP BY result_code) a), '{}'::jsonb),
            'last_cleanup_seconds', COALESCE(EXTRACT(EPOCH FROM now() -
              (SELECT max(last_cleanup_at) FROM public.worker_heartbeats)), 1000000000),
            'workers_alive', (SELECT count(*) FROM public.worker_heartbeats
                              WHERE last_seen_at > now() - interval '60 seconds')
          ) FROM public.jobs
        $fn$;
    """)
    op.execute("ALTER FUNCTION app_private.job_metrics(text[]) OWNER TO prospect_job_claim_owner")
    op.execute("REVOKE ALL ON FUNCTION app_private.job_metrics(text[]) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.job_metrics(text[]) TO prospect_worker")

    op.execute("""
        CREATE FUNCTION app_private.failed_jobs(p_limit integer) RETURNS jsonb
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_result jsonb;
        BEGIN
          IF p_limit < 1 OR p_limit > 100 THEN RAISE EXCEPTION 'Invalid result limit'; END IF;
          SELECT COALESCE(jsonb_agg(jsonb_build_object(
            'id', j.id, 'organization_id', j.organization_id, 'type', j.type,
            'attempt_count', j.attempt_count, 'last_error_code', j.last_error_code,
            'finished_at', j.finished_at) ORDER BY j.finished_at DESC), '[]'::jsonb)
          INTO v_result FROM (
            SELECT id, organization_id, type, attempt_count, last_error_code, finished_at
            FROM public.jobs WHERE status = 'failed' ORDER BY finished_at DESC LIMIT p_limit
          ) j;
          RETURN v_result;
        END $fn$;
    """)
    op.execute("ALTER FUNCTION app_private.failed_jobs(integer) OWNER TO prospect_job_claim_owner")
    op.execute("REVOKE ALL ON FUNCTION app_private.failed_jobs(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.failed_jobs(integer) TO prospect_worker")

    op.execute("""
        CREATE FUNCTION app_private.inspect_job(p_id uuid) RETURNS jsonb
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $fn$
          SELECT jsonb_build_object(
            'id', j.id, 'organization_id', j.organization_id, 'type', j.type,
            'status', j.status, 'replay_of_job_id', j.replay_of_job_id,
            'attempt_count', j.attempt_count, 'last_error_code', j.last_error_code,
            'created_at', j.created_at, 'finished_at', j.finished_at,
            'attempts', COALESCE((SELECT jsonb_agg(jsonb_build_object(
              'number', a.attempt_number, 'started_at', a.started_at,
              'finished_at', a.finished_at, 'result_code', a.result_code)
              ORDER BY a.attempt_number) FROM public.job_attempts a WHERE a.job_id = j.id), '[]'::jsonb)
          ) FROM public.jobs j WHERE j.id = p_id
        $fn$;
    """)
    op.execute("ALTER FUNCTION app_private.inspect_job(uuid) OWNER TO prospect_job_claim_owner")
    op.execute("REVOKE ALL ON FUNCTION app_private.inspect_job(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_private.inspect_job(uuid) TO prospect_worker")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_private.inspect_job(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_private.failed_jobs(integer)")
    op.execute("DROP FUNCTION IF EXISTS app_private.job_metrics(text[])")
    op.execute("DROP FUNCTION IF EXISTS app_private.purge_jobs(integer)")
    op.execute("DROP FUNCTION IF EXISTS app_private.claim_job(text[])")
    op.drop_table("job_events")
    op.drop_table("job_attempts")
    op.drop_table("job_scheduler_state")
    op.drop_table("jobs")
    op.drop_table("worker_heartbeats")
    op.execute("DROP POLICY IF EXISTS memberships_worker_tenant ON public.memberships")
    op.execute("DROP POLICY IF EXISTS organizations_worker_tenant ON public.organizations")
    op.execute("REVOKE SELECT ON public.organizations, public.memberships FROM prospect_worker")
    op.execute("REVOKE SELECT (id, status) ON public.users FROM prospect_worker")
    op.execute("REVOKE EXECUTE ON FUNCTION app_private.current_organization_id() FROM prospect_worker")
    op.execute("REVOKE USAGE ON SCHEMA app_private, public FROM prospect_worker")
