"""Stripe sandbox payment evidence, continuing projection and fenced retries."""

from alembic import op

revision = "20261027_0063"
down_revision = "20261025_0062"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "app_private.project_simulated_billing_event(uuid)",
    "app_private.read_stripe_projection_event(uuid)",
    "app_private.fail_stripe_projection_event(uuid,integer)",
    "app_private.project_stripe_sandbox_event(uuid,integer,jsonb)",
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.subscriptions ADD COLUMN stripe_observed_at timestamptz, ADD COLUMN stripe_paid_until timestamptz"
    )
    op.execute(
        "ALTER TABLE public.stripe_sandbox_checkout_sessions ADD COLUMN provider_subscription_reference varchar(255)"
    )
    op.execute("""
        ALTER TABLE public.stripe_sandbox_checkout_sessions
        ADD CONSTRAINT uq_stripe_checkout_subscription_reference
        UNIQUE (provider_subscription_reference)
    """)
    # Older sandbox snapshots could activate a contract without invoice evidence.
    # Preserve their references, then require a fresh authenticated observation.
    op.execute("""
        UPDATE public.stripe_sandbox_checkout_sessions AS checkout
        SET provider_subscription_reference = subscription.provider_subscription_reference,
            updated_at = clock_timestamp()
        FROM public.billing_events AS event
        JOIN public.billing_event_inbox AS inbox ON inbox.id=event.inbox_id
        JOIN public.subscriptions AS subscription ON subscription.id=event.subscription_id
        WHERE subscription.provider='stripe'
          AND checkout.billing_command_id::text=inbox.normalized_payload->>'checkout_command_id'
          AND checkout.organization_id=subscription.organization_id
          AND checkout.billing_customer_id=subscription.billing_customer_id
          AND checkout.provider_subscription_reference IS NULL
    """)
    op.execute("""
        UPDATE public.organization_plan_contracts AS contract
        SET state='pending',updated_at=clock_timestamp(),version=version+1
        WHERE contract.state IN ('active','suspended') AND EXISTS (
          SELECT 1 FROM public.subscriptions AS subscription
          WHERE subscription.provider='stripe' AND subscription.organization_id=contract.organization_id
            AND subscription.plan_version_id=contract.plan_version_id
        )
    """)
    op.execute("""
        UPDATE public.subscriptions SET state='pending_checkout',grace_policy_version=NULL,
          grace_started_at=NULL,grace_ends_at=NULL,version=version+1,updated_at=clock_timestamp()
        WHERE provider='stripe' AND state<>'canceled'
    """)
    for table in ("billing_event_inbox", "billing_events"):
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT ck_{table}_type")
        op.execute(
            f"ALTER TABLE public.{table} ADD CONSTRAINT ck_{table}_type CHECK (event_type IN "
            "('checkout.completed','subscription.snapshot','invoice.paid','invoice.payment_failed','refund.succeeded','refund.updated'))"
        )
    op.execute("""
        DO $body$ DECLARE definition text; BEGIN
          SELECT pg_get_functiondef('app_private.admit_billing_webhook(text,text,text,text,timestamptz,timestamptz,text,jsonb)'::regprocedure) INTO definition;
          EXECUTE replace(definition, '''refund.succeeded''', '''refund.succeeded'',''refund.updated''');
        END $body$
    """)
    op.execute(
        "REVOKE EXECUTE ON FUNCTION app_private.project_stripe_sandbox_subscription_event(uuid) FROM prospect_worker"
    )
    op.execute("REVOKE EXECUTE ON FUNCTION app_private.project_billing_event(uuid) FROM prospect_worker")
    op.execute("""
        CREATE FUNCTION app_private.project_simulated_billing_event(p_id uuid) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        BEGIN
          IF NOT EXISTS(SELECT 1 FROM public.billing_event_inbox
            WHERE id=p_id AND provider='simulated' AND status='processing') THEN
            RETURN jsonb_build_object('result_code','lost_claim');
          END IF;
          RETURN app_private.project_billing_event(p_id);
        END $fn$;
    """)
    op.execute("""
        CREATE FUNCTION app_private.read_stripe_projection_event(p_id uuid) RETURNS jsonb
        LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
          SELECT jsonb_build_object('payload',normalized_payload,'attempt',attempt_count)
          FROM public.billing_event_inbox WHERE id=p_id AND provider='stripe' AND status='processing'
        $fn$
    """)
    op.execute("""
        CREATE FUNCTION app_private.fail_stripe_projection_event(p_id uuid,p_attempt integer) RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        BEGIN
          PERFORM 1 FROM public.billing_event_inbox WHERE id=p_id AND provider='stripe'
            AND status='processing' AND attempt_count=p_attempt FOR UPDATE;
          IF NOT FOUND THEN RETURN 'lost_claim'; END IF;
          RETURN app_private.fail_billing_event_projection(p_id);
        END $fn$
    """)
    op.execute(r"""
        CREATE FUNCTION app_private.project_stripe_sandbox_event(p_id uuid,p_attempt integer,p_evidence jsonb)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE
          i public.billing_event_inbox%ROWTYPE; c public.stripe_sandbox_checkout_sessions%ROWTYPE;
          s public.subscriptions%ROWTYPE; v jsonb:=p_evidence->'subscription'; inv jsonb:=p_evidence->'invoice';
          observed timestamptz; pstart timestamptz; pend timestamptz; paid boolean:=false;
          next_state text; previous text; cause text; event_id uuid; request_id text; amount bigint;
          grace_start timestamptz; grace_end timestamptz; contract_state text;
        BEGIN
          SELECT * INTO i FROM public.billing_event_inbox WHERE id=p_id FOR UPDATE;
          IF NOT FOUND OR i.provider<>'stripe' OR i.status<>'processing' OR i.attempt_count<>p_attempt
            OR i.processing_started_at < clock_timestamp()-interval '90 seconds' THEN
            RETURN jsonb_build_object('result_code','lost_claim');
          END IF;
          IF p_evidence IS NULL OR jsonb_typeof(v)<>'object' OR octet_length(p_evidence::text)>16384 THEN
            RAISE EXCEPTION 'stripe_evidence_invalid';
          END IF;
          observed:=(p_evidence->>'observed_at')::timestamptz;
          pstart:=(v->>'current_period_start')::timestamptz; pend:=(v->>'current_period_end')::timestamptz;
          IF observed IS NULL OR observed>clock_timestamp()+interval '5 minutes'
            OR pstart IS NULL OR pend IS NULL OR pend<=pstart
            OR (v->>'reference') !~ '^sub_[A-Za-z0-9_]+$' OR (v->>'customer_reference') IS NULL
            OR (v->>'price_reference') IS NULL OR (v->>'currency') NOT IN ('CAD','USD','EUR','XAF')
            OR jsonb_typeof(v->'cancel_at_period_end')<>'boolean' THEN RAISE EXCEPTION 'stripe_evidence_invalid'; END IF;
          observed:=LEAST(observed,clock_timestamp());
          SELECT * INTO c FROM public.stripe_sandbox_checkout_sessions
          WHERE provider_subscription_reference=v->>'reference'
             OR (p_evidence->>'checkout_command_id' IS NOT NULL AND billing_command_id=(p_evidence->>'checkout_command_id')::uuid)
          ORDER BY provider_subscription_reference NULLS LAST LIMIT 1 FOR UPDATE;
          IF NOT FOUND THEN RAISE EXCEPTION 'stripe_mapping_pending'; END IF;
          IF (c.provider_subscription_reference IS NOT NULL AND c.provider_subscription_reference<>v->>'reference')
            OR c.currency<>v->>'currency' OR c.provider_price_reference<>v->>'price_reference'
            OR (p_evidence->>'checkout_reference' IS NOT NULL AND p_evidence->>'checkout_reference'<>c.provider_checkout_reference)
            OR NOT EXISTS (SELECT 1 FROM public.billing_customers WHERE id=c.billing_customer_id
              AND organization_id=c.organization_id AND provider='stripe' AND provider_customer_reference=v->>'customer_reference') THEN
            RAISE EXCEPTION 'stripe_mapping_incompatible';
          END IF;
          SELECT amount_excluding_tax_minor INTO amount FROM public.plan_versions WHERE id=c.plan_version_id AND currency=c.currency;
          IF inv IS NOT NULL AND inv<>'null'::jsonb THEN
            IF (inv->>'amount_minor')::bigint IS DISTINCT FROM amount THEN RAISE EXCEPTION 'stripe_invoice_amount_mismatch'; END IF;
            paid:=COALESCE((inv->>'paid')::boolean,false)
              AND (inv->>'period_start')::timestamptz=pstart AND (inv->>'period_end')::timestamptz=pend;
          END IF;
          SELECT * INTO s FROM public.subscriptions WHERE provider='stripe' AND provider_subscription_reference=v->>'reference' FOR UPDATE;
          IF FOUND AND (s.organization_id<>c.organization_id OR s.billing_customer_id<>c.billing_customer_id
            OR s.plan_version_id<>c.plan_version_id OR s.currency<>c.currency) THEN RAISE EXCEPTION 'stripe_subscription_conflict'; END IF;
          IF NOT FOUND THEN
            INSERT INTO public.subscriptions(organization_id,billing_customer_id,provider,provider_subscription_reference,
              plan_version_id,currency,state,current_period_start,current_period_end,provider_updated_at)
            VALUES(c.organization_id,c.billing_customer_id,'stripe',v->>'reference',c.plan_version_id,c.currency,
              'pending_checkout',pstart,pend,i.provider_created_at) RETURNING * INTO s;
          END IF;
          IF s.stripe_observed_at IS NOT NULL AND observed<=s.stripe_observed_at THEN
            UPDATE public.billing_event_inbox SET status='ignored',last_error_code='stripe_observation_stale',processed_at=clock_timestamp() WHERE id=i.id;
            RETURN jsonb_build_object('result_code','ignored');
          END IF;
          previous:=s.state;
          grace_start:=s.grace_started_at; grace_end:=s.grace_ends_at;
          IF s.state='canceled' OR v->>'provider_status' IN ('canceled','incomplete_expired') THEN
            next_state:='canceled'; cause:='cancellation_confirmed';
          ELSIF paid AND v->>'provider_status'='active' AND pend>clock_timestamp() THEN
            next_state:=CASE WHEN (v->>'cancel_at_period_end')::boolean THEN 'canceling' ELSE 'active' END;
            cause:=CASE WHEN next_state='canceling' THEN 'cancellation_scheduled' ELSE 'invoice_paid' END;
            grace_start:=NULL; grace_end:=NULL;
          ELSIF s.stripe_paid_until IS NOT NULL AND v->>'provider_status' IN ('past_due','unpaid') THEN
            grace_start:=COALESCE(grace_start,LEAST(clock_timestamp(),GREATEST(i.provider_created_at,s.stripe_paid_until)));
            grace_end:=grace_start+interval '7 days';
            next_state:=CASE WHEN grace_end<=clock_timestamp() THEN 'suspended' ELSE 'grace_period' END;
            cause:=CASE WHEN next_state='suspended' THEN 'grace_period_expired' ELSE 'grace_period_started' END;
          ELSE
            next_state:=CASE WHEN s.stripe_paid_until IS NULL THEN 'pending_checkout' ELSE 'suspended' END;
            cause:='payment_failed';
          END IF;
          UPDATE public.subscriptions SET state=next_state,current_period_start=pstart,current_period_end=pend,
            cancel_at_period_end=(v->>'cancel_at_period_end')::boolean,stripe_observed_at=observed,
            stripe_paid_until=CASE WHEN paid AND v->>'provider_status'='active' AND pend>clock_timestamp()
              THEN GREATEST(stripe_paid_until,pend) ELSE stripe_paid_until END,
            grace_policy_version=CASE WHEN grace_start IS NULL THEN NULL ELSE 1 END,
            grace_started_at=grace_start,grace_ends_at=grace_end,
            provider_updated_at=GREATEST(provider_updated_at,i.provider_created_at),
            provider_version=provider_version+1,version=version+1,updated_at=clock_timestamp() WHERE id=s.id;
          UPDATE public.stripe_sandbox_checkout_sessions SET provider_subscription_reference=v->>'reference',
            completed_at=COALESCE(completed_at,clock_timestamp()),updated_at=clock_timestamp() WHERE id=c.id;
          INSERT INTO public.billing_events(organization_id,inbox_id,subscription_id,provider,provider_event_id,event_type,schema_version,normalized_payload,occurred_at)
          VALUES(c.organization_id,i.id,s.id,'stripe',i.provider_event_id,
            CASE WHEN i.event_type='refund.updated' AND p_evidence#>>'{refund,status}'='succeeded' THEN 'refund.succeeded' ELSE i.event_type END,
            1,p_evidence,i.provider_created_at) RETURNING id INTO event_id;
          IF previous<>next_state THEN
            INSERT INTO public.subscription_transitions(organization_id,subscription_id,source_billing_event_id,previous_state,next_state,cause,occurred_at)
            VALUES(c.organization_id,s.id,event_id,previous,next_state,cause,observed);
          END IF;
          contract_state:=CASE WHEN next_state IN ('active','canceling','grace_period') THEN 'active'
            WHEN next_state='canceled' THEN 'ended' WHEN next_state='suspended' THEN 'suspended' ELSE 'pending' END;
          UPDATE public.organization_plan_contracts SET state=contract_state,version=version+1,updated_at=clock_timestamp()
          WHERE organization_id=c.organization_id AND plan_version_id=c.plan_version_id AND currency=c.currency
            AND state<>contract_state AND state<>'ended';
          request_id:='billing-inbox-'||i.id::text;
          PERFORM set_config('app.organization_id',c.organization_id::text,true);
          PERFORM set_config('app.request_id',request_id,true);
          PERFORM app_private.append_audit_event(gen_random_uuid(),'tenant',c.organization_id,'system',NULL,
            'billing.subscription_transition_applied','subscription',s.id,request_id,request_id,'worker',
            jsonb_build_object('event_type',i.event_type,'previous_state',previous,'next_state',next_state),1::smallint);
          UPDATE public.billing_event_inbox SET status='processed',last_error_code=NULL,processed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=i.id;
          RETURN jsonb_build_object('result_code','processed');
        END $fn$;
    """)
    for function in _FUNCTIONS:
        op.execute(f"ALTER FUNCTION {function} OWNER TO prospect_rls_definer")
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO prospect_worker")


def downgrade() -> None:
    # Do not erase financial history to make a downgrade pass.
    op.execute("""DO $fn$ BEGIN
      IF EXISTS(SELECT 1 FROM public.billing_event_inbox WHERE event_type='refund.updated')
        OR EXISTS(SELECT 1 FROM public.billing_events WHERE event_type='refund.updated') THEN
        RAISE EXCEPTION 'stripe_history_requires_forward_migration'; END IF;
      END $fn$;""")
    for function in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {function}")
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_private.project_stripe_sandbox_subscription_event(uuid) TO prospect_worker"
    )
    op.execute("GRANT EXECUTE ON FUNCTION app_private.project_billing_event(uuid) TO prospect_worker")
    op.execute("ALTER TABLE public.stripe_sandbox_checkout_sessions DROP COLUMN provider_subscription_reference")
    op.execute("ALTER TABLE public.subscriptions DROP COLUMN stripe_observed_at, DROP COLUMN stripe_paid_until")
    for table in ("billing_event_inbox", "billing_events"):
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT ck_{table}_type")
        op.execute(
            f"ALTER TABLE public.{table} ADD CONSTRAINT ck_{table}_type CHECK (event_type IN "
            "('checkout.completed','subscription.snapshot','invoice.paid','invoice.payment_failed','refund.succeeded'))"
        )
    op.execute("""DO $body$ DECLARE definition text; BEGIN
      SELECT pg_get_functiondef('app_private.admit_billing_webhook(text,text,text,text,timestamptz,timestamptz,text,jsonb)'::regprocedure) INTO definition;
      EXECUTE replace(definition, '''refund.succeeded'',''refund.updated''', '''refund.succeeded''');
      END $body$;""")
