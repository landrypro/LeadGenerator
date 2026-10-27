"""Durable Stripe replay windows and daily subscription observations."""

from alembic import op

revision = "20261027_0064"
down_revision = "20261027_0063"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "app_private.claim_stripe_sync()",
    "app_private.advance_stripe_sync(text,uuid,text,boolean)",
    "app_private.fail_stripe_sync(text,uuid,text)",
    "app_private.read_stripe_sync_subscriptions(uuid,timestamptz)",
    "app_private.admit_stripe_sync_event(text,text,text,timestamptz,jsonb)",
)


def upgrade() -> None:
    script = """
      CREATE TABLE public.stripe_sandbox_sync (
        kind varchar(16) PRIMARY KEY CHECK (kind IN ('events','subscriptions')),
        window_start timestamptz, window_end timestamptz, last_window_end timestamptz,
        cursor_reference varchar(255), lease_token uuid, lease_until timestamptz,
        next_run_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_error_code varchar(64), completed_at timestamptz
      );
      INSERT INTO public.stripe_sandbox_sync(kind) VALUES('events'),('subscriptions');
      ALTER TABLE public.stripe_sandbox_sync ENABLE ROW LEVEL SECURITY;
      ALTER TABLE public.stripe_sandbox_sync FORCE ROW LEVEL SECURITY;
      REVOKE ALL ON public.stripe_sandbox_sync FROM PUBLIC,prospect_app,prospect_worker;
      GRANT SELECT,UPDATE ON public.stripe_sandbox_sync TO prospect_rls_definer;

      CREATE FUNCTION app_private.claim_stripe_sync() RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public,pg_temp AS $fn$
      DECLARE v public.stripe_sandbox_sync%ROWTYPE;
      BEGIN
        SELECT * INTO v FROM public.stripe_sandbox_sync
        WHERE next_run_at<=clock_timestamp() AND (lease_until IS NULL OR lease_until<clock_timestamp())
        ORDER BY next_run_at,kind FOR UPDATE SKIP LOCKED LIMIT 1;
        IF NOT FOUND THEN RETURN NULL; END IF;
        UPDATE public.stripe_sandbox_sync SET lease_token=gen_random_uuid(),lease_until=clock_timestamp()+interval '90 seconds',
          window_start=COALESCE(window_start,last_window_end-interval '5 minutes',clock_timestamp()-interval '28 days'),
          window_end=COALESCE(window_end,date_trunc('second',clock_timestamp()-interval '1 minute'))
        WHERE kind=v.kind RETURNING * INTO v;
        RETURN to_jsonb(v);
      END $fn$;
      CREATE FUNCTION app_private.advance_stripe_sync(p_kind text,p_token uuid,p_cursor text,p_done boolean)
      RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
      BEGIN
        UPDATE public.stripe_sandbox_sync SET cursor_reference=CASE WHEN p_done THEN NULL ELSE p_cursor END,
          last_window_end=CASE WHEN p_done THEN window_end ELSE last_window_end END,
          window_start=CASE WHEN p_done THEN NULL ELSE window_start END,
          window_end=CASE WHEN p_done THEN NULL ELSE window_end END,
          completed_at=CASE WHEN p_done THEN clock_timestamp() ELSE completed_at END,
          next_run_at=CASE WHEN p_done THEN clock_timestamp()+CASE WHEN kind='events' THEN interval '15 minutes' ELSE interval '1 day' END ELSE clock_timestamp() END,
          lease_token=NULL,lease_until=NULL,last_error_code=NULL
        WHERE kind=p_kind AND lease_token=p_token AND lease_until>clock_timestamp();
        RETURN FOUND;
      END $fn$;
      CREATE FUNCTION app_private.fail_stripe_sync(p_kind text,p_token uuid,p_code text)
      RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
      BEGIN
        IF p_code NOT IN ('stripe_sync_unavailable','stripe_event_history_expired') THEN RETURN false; END IF;
        UPDATE public.stripe_sandbox_sync SET lease_token=NULL,lease_until=NULL,last_error_code=p_code,
          next_run_at=clock_timestamp()+CASE WHEN p_code='stripe_event_history_expired'
            THEN interval '1 day' ELSE interval '1 minute' END
        WHERE kind=p_kind AND lease_token=p_token;
        RETURN FOUND;
      END $fn$;
      CREATE FUNCTION app_private.read_stripe_sync_subscriptions(p_after uuid,p_until timestamptz)
      RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        SELECT COALESCE(jsonb_agg(to_jsonb(v)),'[]'::jsonb) FROM (
          SELECT id,provider_subscription_reference AS reference FROM public.subscriptions
          WHERE provider='stripe' AND created_at<=p_until AND (p_after IS NULL OR id>p_after)
          ORDER BY id LIMIT 5
        ) v
      $fn$;
      CREATE FUNCTION app_private.admit_stripe_sync_event(p_event text,p_type text,p_object text,p_created timestamptz,p_payload jsonb)
      RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
      DECLARE v public.billing_event_inbox%ROWTYPE; result jsonb; digest text;
      BEGIN
        SELECT * INTO v FROM public.billing_event_inbox WHERE provider='stripe' AND provider_event_id=p_event FOR UPDATE;
        IF FOUND THEN
          IF v.event_type<>p_type OR v.provider_object_reference<>p_object OR v.provider_created_at<>p_created
            OR (v.normalized_payload-'provider_event_kind')<>(p_payload-'provider_event_kind') THEN RETURN false; END IF;
          IF v.status IN ('dead_letter','ignored') AND v.last_error_code IN
            ('projection_attempts_exhausted','stripe_mapping_missing','stripe_mapping_incompatible') THEN
            UPDATE public.billing_event_inbox SET status='admitted',attempt_count=0,next_attempt_at=NULL,
              processing_started_at=NULL,processed_at=NULL,updated_at=clock_timestamp() WHERE id=v.id;
          END IF;
          RETURN true;
        END IF;
        digest:=encode(sha256(convert_to(p_payload::text,'UTF8')),'hex');
        result:=app_private.admit_billing_webhook('stripe',p_event,p_type,p_object,p_created,clock_timestamp(),digest,p_payload);
        RETURN result->>'code' IN ('admitted','duplicate');
      END $fn$;
    """
    preamble, *functions = script.split("CREATE FUNCTION")
    for statement in preamble.split(";"):
        if statement.strip():
            op.execute(statement.strip())
    for definition in functions:
        op.execute("CREATE FUNCTION " + definition.strip().removesuffix(";"))
    for function in _FUNCTIONS:
        op.execute(f"ALTER FUNCTION {function} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO prospect_worker")


def downgrade() -> None:
    for function in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    op.execute("DROP TABLE public.stripe_sandbox_sync")
