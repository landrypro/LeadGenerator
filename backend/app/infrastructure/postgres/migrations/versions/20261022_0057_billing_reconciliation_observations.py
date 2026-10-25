"""Enregistrement conditionnel d'observations de réconciliation simulée.

Revision ID: 20261022_0057
Revises: 20261021_0056
"""

from alembic import op

revision = "20261022_0057"
down_revision = "20261021_0056"
branch_labels = None
depends_on = None

_SIGNATURE = "app_private.record_billing_reconciliation_observation(uuid,uuid,uuid,integer,text)"
_SCHEDULE_SIGNATURE = "app_private.schedule_billing_reconciliation_window(text,timestamptz,timestamptz)"
_LAST_WINDOW_SIGNATURE = "app_private.last_billing_reconciliation_window_end(text)"
_CLAIM_SIGNATURE = "app_private.claim_billing_reconciliation_run()"
_RENEW_SIGNATURE = "app_private.renew_billing_reconciliation_run(uuid,uuid)"
_ADVANCE_SIGNATURE = "app_private.advance_billing_reconciliation_run(uuid,uuid,uuid,uuid,integer,text)"
_READ_SIGNATURE = "app_private.read_billing_reconciliation_candidate(uuid,uuid)"
_COMPLETE_SIGNATURE = "app_private.complete_billing_reconciliation_run(uuid,uuid)"
_RELEASE_SIGNATURE = "app_private.release_billing_reconciliation_run(uuid,uuid)"
_MANUAL_SIGNATURE = "app_private.request_manual_billing_reconciliation(uuid,text,text)"


def upgrade() -> None:
    op.execute("ALTER TABLE public.billing_reconciliation_runs ADD COLUMN lease_token uuid")
    op.execute("ALTER TABLE public.billing_reconciliation_runs ADD COLUMN lease_expires_at timestamptz")
    op.execute(
        "ALTER TABLE public.billing_reconciliation_runs ADD COLUMN requested_by uuid REFERENCES public.users(id) ON DELETE RESTRICT"
    )
    op.execute("ALTER TABLE public.billing_reconciliation_runs ADD COLUMN reason_code varchar(24)")
    op.execute("ALTER TABLE public.billing_reconciliation_runs ADD COLUMN request_key_digest char(64)")
    op.execute(
        "ALTER TABLE public.billing_reconciliation_runs ADD CONSTRAINT ck_billing_reconciliation_runs_manual_request CHECK ("
        "(run_kind <> 'manual' AND requested_by IS NULL AND reason_code IS NULL AND request_key_digest IS NULL) OR "
        "(run_kind = 'manual' AND ((requested_by IS NULL AND reason_code IS NULL AND request_key_digest IS NULL) OR "
        "(requested_by IS NOT NULL AND reason_code IS NOT NULL "
        "AND reason_code IN ('payment_uncertain','state_mismatch','operator_review') "
        "AND request_key_digest IS NOT NULL AND request_key_digest ~ '^[a-f0-9]{64}$'))))"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_billing_reconciliation_manual_key ON public.billing_reconciliation_runs "
        "(requested_by,request_key_digest) WHERE request_key_digest IS NOT NULL"
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.request_manual_billing_reconciliation(p_org uuid,p_reason text,p_key text)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_actor uuid:=app_private.current_actor_id(); v_request text:=current_setting('app.request_id',true);
                v_existing public.billing_reconciliation_runs%ROWTYPE; v_id uuid; v_now timestamptz:=clock_timestamp();
        BEGIN
          IF v_actor IS NULL OR NOT EXISTS (
            SELECT 1 FROM public.users WHERE id=v_actor AND status='active' AND platform_role='platform_admin'
          ) THEN RETURN jsonb_build_object('code','billing_capability_required'); END IF;
          IF p_org IS NULL OR p_reason IS NULL OR p_reason NOT IN ('payment_uncertain','state_mismatch','operator_review')
             OR p_key IS NULL OR p_key !~ '^[a-f0-9]{64}$' OR v_request IS NULL OR btrim(v_request)='' THEN
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          PERFORM pg_advisory_xact_lock(hashtextextended('billing-reconciliation-manual:'||v_actor::text||':'||p_key,0));
          SELECT * INTO v_existing FROM public.billing_reconciliation_runs
          WHERE requested_by=v_actor AND request_key_digest=p_key FOR UPDATE;
          IF FOUND THEN
            IF v_existing.organization_id<>p_org OR v_existing.reason_code<>p_reason THEN
              RETURN jsonb_build_object('code','billing_command_conflict');
            END IF;
            RETURN jsonb_build_object('code','replayed','run_id',v_existing.id);
          END IF;
          IF NOT EXISTS (SELECT 1 FROM public.organizations WHERE id=p_org AND status='active') THEN
            RETURN jsonb_build_object('code','billing_state_unknown');
          END IF;
          INSERT INTO public.billing_reconciliation_runs
            (organization_id,run_kind,status,window_started_at,window_ended_at,requested_by,reason_code,request_key_digest)
          VALUES(p_org,'manual','pending',v_now-interval '1 second',v_now,v_actor,p_reason,p_key) RETURNING id INTO v_id;
          PERFORM app_private.append_audit_event(gen_random_uuid(),'platform',NULL,'user',v_actor,
            'billing.reconciliation_requested','billing_reconciliation_run',v_id,v_request,v_request,'api',
            jsonb_build_object('reason_code',p_reason,'organization_id',p_org),1::smallint);
          RETURN jsonb_build_object('code','reserved','run_id',v_id);
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_MANUAL_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_MANUAL_SIGNATURE} FROM PUBLIC, prospect_worker")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_MANUAL_SIGNATURE} TO prospect_app")
    op.execute(
        "ALTER TABLE public.billing_reconciliation_runs ADD CONSTRAINT ck_billing_reconciliation_runs_lease CHECK ("
        "(lease_token IS NULL AND lease_expires_at IS NULL) OR "
        "(lease_token IS NOT NULL AND lease_expires_at IS NOT NULL AND status='running'))"
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.claim_billing_reconciliation_run()
        RETURNS TABLE(run_id uuid, lease_token uuid, organization_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_id uuid; v_token uuid := gen_random_uuid();
        BEGIN
          SELECT r.id INTO v_id FROM public.billing_reconciliation_runs r
          WHERE r.status='pending' OR (r.status='running' AND
                (r.lease_expires_at IS NULL OR r.lease_expires_at<=clock_timestamp()))
          ORDER BY r.created_at,r.id FOR UPDATE SKIP LOCKED LIMIT 1;
          IF NOT FOUND THEN RETURN; END IF;
          RETURN QUERY UPDATE public.billing_reconciliation_runs r
            SET status='running',started_at=coalesce(r.started_at,clock_timestamp()),
                lease_token=v_token,lease_expires_at=clock_timestamp()+interval '2 minutes'
            WHERE r.id=v_id RETURNING r.id,r.lease_token,r.organization_id;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_CLAIM_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_CLAIM_SIGNATURE} FROM PUBLIC, prospect_app")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_CLAIM_SIGNATURE} TO prospect_worker")
    op.execute(
        r"""
        CREATE FUNCTION app_private.renew_billing_reconciliation_run(p_run_id uuid,p_token uuid)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        BEGIN
          IF p_run_id IS NULL OR p_token IS NULL THEN RETURN false; END IF;
          UPDATE public.billing_reconciliation_runs SET lease_expires_at=clock_timestamp()+interval '2 minutes'
          WHERE id=p_run_id AND status='running' AND lease_token=p_token AND lease_expires_at>clock_timestamp();
          RETURN FOUND;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_RENEW_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_RENEW_SIGNATURE} FROM PUBLIC, prospect_app")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_RENEW_SIGNATURE} TO prospect_worker")
    op.execute(
        r"""
        CREATE FUNCTION app_private.release_billing_reconciliation_run(p_run_id uuid,p_token uuid)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        BEGIN
          IF p_run_id IS NULL OR p_token IS NULL THEN RETURN false; END IF;
          UPDATE public.billing_reconciliation_runs SET status='pending',lease_token=NULL,lease_expires_at=NULL
          WHERE id=p_run_id AND status='running' AND lease_token=p_token AND lease_expires_at>clock_timestamp();
          RETURN FOUND;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_RELEASE_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_RELEASE_SIGNATURE} FROM PUBLIC, prospect_app")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_RELEASE_SIGNATURE} TO prospect_worker")
    op.execute(
        r"""
        CREATE FUNCTION app_private.last_billing_reconciliation_window_end(p_kind text)
        RETURNS timestamptz LANGUAGE sql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
          SELECT max(window_ended_at) FROM public.billing_reconciliation_runs
          WHERE organization_id IS NULL AND run_kind=p_kind AND p_kind IN ('incremental','exhaustive')
        $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_LAST_WINDOW_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_LAST_WINDOW_SIGNATURE} FROM PUBLIC, prospect_app")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_LAST_WINDOW_SIGNATURE} TO prospect_worker")
    op.execute(
        r"""
        CREATE FUNCTION app_private.schedule_billing_reconciliation_window(
          p_kind text, p_started_at timestamptz, p_ended_at timestamptz
        ) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_run uuid; v_last_end timestamptz; v_interval interval; v_seconds integer;
        BEGIN
          IF p_kind IS NULL OR p_kind NOT IN ('incremental','exhaustive')
             OR p_started_at IS NULL OR p_ended_at IS NULL THEN
            RETURN NULL;
          END IF;
          IF p_kind='incremental' THEN
            v_interval := interval '15 minutes'; v_seconds := 900;
          ELSE
            v_interval := interval '1 day'; v_seconds := 86400;
          END IF;
          IF p_ended_at-p_started_at <> v_interval OR p_ended_at > clock_timestamp()
             OR extract(epoch FROM p_started_at) <> trunc(extract(epoch FROM p_started_at))
             OR mod(extract(epoch FROM p_started_at)::bigint, v_seconds) <> 0 THEN
            RETURN NULL;
          END IF;
          PERFORM pg_advisory_xact_lock(hashtextextended('billing-reconciliation-' || p_kind,0));
          SELECT id INTO v_run FROM public.billing_reconciliation_runs
            WHERE organization_id IS NULL AND run_kind=p_kind
              AND window_started_at=p_started_at AND window_ended_at=p_ended_at
            ORDER BY created_at,id LIMIT 1;
          IF FOUND THEN RETURN v_run; END IF;
          SELECT max(window_ended_at) INTO v_last_end FROM public.billing_reconciliation_runs
            WHERE organization_id IS NULL AND run_kind=p_kind;
          IF v_last_end IS NOT NULL AND v_last_end <> p_started_at THEN RETURN NULL; END IF;
          INSERT INTO public.billing_reconciliation_runs
            (organization_id,run_kind,status,window_started_at,window_ended_at)
          VALUES (NULL,p_kind,'pending',p_started_at,p_ended_at) RETURNING id INTO v_run;
          RETURN v_run;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_SCHEDULE_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_SCHEDULE_SIGNATURE} FROM PUBLIC, prospect_app")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_SCHEDULE_SIGNATURE} TO prospect_worker")
    op.execute(
        r"""
        CREATE FUNCTION app_private.record_billing_reconciliation_observation(
          p_run_id uuid, p_organization_id uuid, p_subscription_id uuid, p_expected_version integer, p_code text
        ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          v_run public.billing_reconciliation_runs%ROWTYPE;
          v_subscription public.subscriptions%ROWTYPE;
          v_existing public.billing_reconciliation_differences%ROWTYPE;
          v_difference_id uuid;
          v_request text;
        BEGIN
          IF p_run_id IS NULL OR p_organization_id IS NULL OR p_subscription_id IS NULL
             OR p_expected_version IS NULL OR p_expected_version < 1 OR p_code IS NULL
             OR p_code NOT IN ('in_sync','local_stale','provider_stale','mapping_missing',
                               'currency_mismatch','price_mismatch','unresolved') THEN
            RETURN false;
          END IF;
          SELECT * INTO v_run FROM public.billing_reconciliation_runs WHERE id=p_run_id FOR UPDATE;
          IF NOT FOUND OR v_run.status <> 'running'
             OR (v_run.organization_id IS NOT NULL AND v_run.organization_id <> p_organization_id) THEN
            RETURN false;
          END IF;
          SELECT * INTO v_subscription FROM public.subscriptions
            WHERE id=p_subscription_id AND organization_id=p_organization_id FOR UPDATE;
          IF NOT FOUND OR v_subscription.provider <> 'simulated' OR v_subscription.version <> p_expected_version THEN
            RETURN false;
          END IF;
          SELECT * INTO v_existing FROM public.billing_reconciliation_differences
            WHERE run_id=p_run_id AND organization_id=p_organization_id AND subscription_id=p_subscription_id
            ORDER BY created_at,id LIMIT 1;
          IF FOUND THEN
            RETURN v_existing.difference_code=p_code AND v_existing.resolved_at IS NULL;
          END IF;
          INSERT INTO public.billing_reconciliation_differences
            (organization_id,run_id,subscription_id,difference_code)
          VALUES (p_organization_id,p_run_id,p_subscription_id,p_code)
          RETURNING id INTO v_difference_id;
          IF p_code <> 'in_sync' THEN
            v_request := 'billing-reconciliation-' || p_run_id::text;
            PERFORM set_config('app.organization_id',p_organization_id::text,true);
            PERFORM set_config('app.actor_id','',true);
            PERFORM set_config('app.request_id',v_request,true);
            PERFORM app_private.append_audit_event(
              gen_random_uuid(),'tenant',p_organization_id,'system',NULL,
              'billing.reconciliation_difference_detected','billing_reconciliation_difference',v_difference_id,
              v_request,v_request,'worker',jsonb_build_object('difference_code',p_code),1::smallint
            );
          END IF;
          RETURN true;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_SIGNATURE} FROM PUBLIC, prospect_app")
    op.execute(
        r"""
        CREATE FUNCTION app_private.advance_billing_reconciliation_run(
          p_run uuid,p_token uuid,p_org uuid,p_subscription uuid,p_version integer,p_code text
        ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_run public.billing_reconciliation_runs%ROWTYPE; v_next uuid;
        BEGIN
          IF p_run IS NULL OR p_token IS NULL OR p_org IS NULL OR p_subscription IS NULL THEN RETURN false; END IF;
          SELECT * INTO v_run FROM public.billing_reconciliation_runs WHERE id=p_run FOR UPDATE;
          IF NOT FOUND OR v_run.status<>'running' OR v_run.lease_token IS DISTINCT FROM p_token
             OR v_run.lease_expires_at IS NULL OR v_run.lease_expires_at<=clock_timestamp()
             OR (v_run.organization_id IS NOT NULL AND v_run.organization_id<>p_org) THEN RETURN false; END IF;
          IF v_run.cursor_reference IS DISTINCT FROM p_subscription::text THEN
            SELECT id INTO v_next FROM public.subscriptions
            WHERE provider='simulated' AND created_at<=v_run.started_at
              AND (v_run.organization_id IS NULL OR organization_id=v_run.organization_id)
              AND (v_run.cursor_reference IS NULL OR id>v_run.cursor_reference::uuid)
            ORDER BY id LIMIT 1;
            IF v_next IS DISTINCT FROM p_subscription THEN RETURN false; END IF;
          END IF;
          BEGIN
            IF NOT app_private.record_billing_reconciliation_observation(
              p_run,p_org,p_subscription,p_version,p_code
            ) THEN RETURN false; END IF;
            IF v_run.lease_expires_at<=clock_timestamp() THEN
              RAISE EXCEPTION USING ERRCODE='P4401',MESSAGE='billing_reconciliation_lease_expired';
            END IF;
            UPDATE public.billing_reconciliation_runs SET cursor_reference=p_subscription::text WHERE id=p_run;
          EXCEPTION WHEN SQLSTATE 'P4401' THEN RETURN false;
          END;
          RETURN true;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_ADVANCE_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_ADVANCE_SIGNATURE} FROM PUBLIC, prospect_app")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_ADVANCE_SIGNATURE} TO prospect_worker")
    op.execute(
        r"""
        CREATE FUNCTION app_private.read_billing_reconciliation_candidate(p_run uuid,p_token uuid)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_run public.billing_reconciliation_runs%ROWTYPE; v_candidate record;
        BEGIN
          SELECT * INTO v_run FROM public.billing_reconciliation_runs WHERE id=p_run;
          IF NOT FOUND OR p_token IS NULL OR v_run.status<>'running'
             OR v_run.lease_token IS DISTINCT FROM p_token OR v_run.lease_expires_at IS NULL
             OR v_run.lease_expires_at<=clock_timestamp() THEN
            RETURN jsonb_build_object('status','lease_lost');
          END IF;
          SELECT s.*,c.provider_customer_reference INTO v_candidate FROM public.subscriptions s
          JOIN public.billing_customers c ON c.id=s.billing_customer_id AND c.organization_id=s.organization_id
          WHERE s.provider='simulated' AND s.created_at<=v_run.started_at
            AND (v_run.organization_id IS NULL OR s.organization_id=v_run.organization_id)
            AND (v_run.cursor_reference IS NULL OR s.id>v_run.cursor_reference::uuid)
          ORDER BY s.id LIMIT 1;
          IF NOT FOUND THEN RETURN jsonb_build_object('status','exhausted'); END IF;
          RETURN jsonb_build_object(
            'status','candidate','run_id',p_run,'organization_id',v_candidate.organization_id,
            'subscription_id',v_candidate.id,'local_version',v_candidate.version,
            'subscription_reference',v_candidate.provider_subscription_reference,
            'customer_reference',v_candidate.provider_customer_reference,
            'price_reference','sim_price_' || replace(v_candidate.plan_version_id::text,'-',''),
            'state',v_candidate.state,'currency',v_candidate.currency,
            'period_start',v_candidate.current_period_start,'period_end',v_candidate.current_period_end,
            'cancel_at_period_end',v_candidate.cancel_at_period_end,'provider_updated_at',v_candidate.provider_updated_at
          );
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_READ_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_READ_SIGNATURE} FROM PUBLIC, prospect_app")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_READ_SIGNATURE} TO prospect_worker")
    op.execute(
        r"""
        CREATE FUNCTION app_private.complete_billing_reconciliation_run(p_run uuid,p_token uuid)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_run public.billing_reconciliation_runs%ROWTYPE;
        BEGIN
          SELECT * INTO v_run FROM public.billing_reconciliation_runs WHERE id=p_run FOR UPDATE;
          IF NOT FOUND OR p_token IS NULL OR v_run.status<>'running'
             OR v_run.lease_token IS DISTINCT FROM p_token OR v_run.lease_expires_at IS NULL
             OR v_run.lease_expires_at<=clock_timestamp() THEN RETURN false; END IF;
          IF EXISTS (
            SELECT 1 FROM public.subscriptions s WHERE s.provider='simulated' AND s.created_at<=v_run.started_at
              AND (v_run.organization_id IS NULL OR s.organization_id=v_run.organization_id)
              AND (v_run.cursor_reference IS NULL OR s.id>v_run.cursor_reference::uuid)
          ) THEN RETURN false; END IF;
          UPDATE public.billing_reconciliation_runs SET status='completed',completed_at=clock_timestamp(),
            lease_token=NULL,lease_expires_at=NULL WHERE id=p_run AND lease_expires_at>clock_timestamp();
          RETURN FOUND;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_COMPLETE_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_COMPLETE_SIGNATURE} FROM PUBLIC, prospect_app")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_COMPLETE_SIGNATURE} TO prospect_worker")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_MANUAL_SIGNATURE} FROM prospect_app")
    op.execute(f"DROP FUNCTION {_MANUAL_SIGNATURE}")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_COMPLETE_SIGNATURE} FROM prospect_worker")
    op.execute(f"DROP FUNCTION {_COMPLETE_SIGNATURE}")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_READ_SIGNATURE} FROM prospect_worker")
    op.execute(f"DROP FUNCTION {_READ_SIGNATURE}")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_ADVANCE_SIGNATURE} FROM prospect_worker")
    op.execute(f"DROP FUNCTION {_ADVANCE_SIGNATURE}")
    op.execute(f"DROP FUNCTION {_SIGNATURE}")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_SCHEDULE_SIGNATURE} FROM prospect_worker")
    op.execute(f"DROP FUNCTION {_SCHEDULE_SIGNATURE}")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_LAST_WINDOW_SIGNATURE} FROM prospect_worker")
    op.execute(f"DROP FUNCTION {_LAST_WINDOW_SIGNATURE}")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_RELEASE_SIGNATURE} FROM prospect_worker")
    op.execute(f"DROP FUNCTION {_RELEASE_SIGNATURE}")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_RENEW_SIGNATURE} FROM prospect_worker")
    op.execute(f"DROP FUNCTION {_RENEW_SIGNATURE}")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_CLAIM_SIGNATURE} FROM prospect_worker")
    op.execute(f"DROP FUNCTION {_CLAIM_SIGNATURE}")
    op.execute("ALTER TABLE public.billing_reconciliation_runs DROP CONSTRAINT ck_billing_reconciliation_runs_lease")
    op.execute("ALTER TABLE public.billing_reconciliation_runs DROP COLUMN lease_expires_at")
    op.execute("ALTER TABLE public.billing_reconciliation_runs DROP COLUMN lease_token")
    op.execute("DROP INDEX public.uq_billing_reconciliation_manual_key")
    op.execute(
        "ALTER TABLE public.billing_reconciliation_runs DROP CONSTRAINT ck_billing_reconciliation_runs_manual_request"
    )
    op.execute("ALTER TABLE public.billing_reconciliation_runs DROP COLUMN request_key_digest")
    op.execute("ALTER TABLE public.billing_reconciliation_runs DROP COLUMN reason_code")
    op.execute("ALTER TABLE public.billing_reconciliation_runs DROP COLUMN requested_by")
