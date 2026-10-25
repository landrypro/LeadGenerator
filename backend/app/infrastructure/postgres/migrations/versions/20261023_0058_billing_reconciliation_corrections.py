"""Preuves partagees et corrections auditees de reconciliation P53-08.

Revision ID: 20261023_0058
Revises: 20261022_0057
Create Date: 2026-10-23
"""

from alembic import op

revision = "20261023_0058"
down_revision = "20261022_0057"
branch_labels = None
depends_on = None

_RECORD_CHECKOUT = (
    "app_private.record_simulated_billing_checkout_snapshot(text,text,text,text,timestamptz,timestamptz,timestamptz)"
)
_RECORD_WEBHOOK = "app_private.record_simulated_billing_webhook_snapshot(text,text)"
_READ_SNAPSHOT = "app_private.read_simulated_billing_provider_subscription(text)"
_APPLY_CORRECTION = "app_private.apply_simulated_billing_reconciliation_correction()"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.simulated_billing_provider_subscriptions (
          provider_subscription_reference varchar(255) PRIMARY KEY,
          provider_customer_reference varchar(255) NOT NULL,
          provider_price_reference varchar(255) NOT NULL,
          currency varchar(3) NOT NULL,
          state varchar(24) NOT NULL,
          current_period_start timestamptz NOT NULL,
          current_period_end timestamptz NOT NULL,
          cancel_at_period_end boolean NOT NULL DEFAULT false,
          provider_updated_at timestamptz NOT NULL,
          source_inbox_id uuid NULL REFERENCES public.billing_event_inbox(id) ON DELETE RESTRICT,
          ambiguous boolean NOT NULL DEFAULT false,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT ck_simulated_billing_provider_subscriptions_reference CHECK (
            char_length(btrim(provider_subscription_reference)) BETWEEN 1 AND 255
          ),
          CONSTRAINT ck_simulated_billing_provider_subscriptions_customer CHECK (
            char_length(btrim(provider_customer_reference)) BETWEEN 1 AND 255
          ),
          CONSTRAINT ck_simulated_billing_provider_subscriptions_price CHECK (
            char_length(btrim(provider_price_reference)) BETWEEN 1 AND 255
          ),
          CONSTRAINT ck_simulated_billing_provider_subscriptions_currency CHECK (
            currency IN ('CAD','USD','EUR','XAF')
          ),
          CONSTRAINT ck_simulated_billing_provider_subscriptions_state CHECK (
            state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling','canceled')
          ),
          CONSTRAINT ck_simulated_billing_provider_subscriptions_period CHECK (
            current_period_end > current_period_start
          ),
          CONSTRAINT uq_simulated_provider_subscriptions_source_inbox UNIQUE (source_inbox_id)
        )
        """
    )
    op.execute("ALTER TABLE public.simulated_billing_provider_subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.simulated_billing_provider_subscriptions FORCE ROW LEVEL SECURITY")
    op.execute(
        "REVOKE ALL ON public.simulated_billing_provider_subscriptions FROM PUBLIC, prospect_app, prospect_worker"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON public.simulated_billing_provider_subscriptions TO prospect_rls_definer"
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.record_simulated_billing_checkout_snapshot(
          p_subscription text,p_customer text,p_price text,p_currency text,
          p_period_start timestamptz,p_period_end timestamptz,p_provider_updated_at timestamptz
        ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        BEGIN
          IF p_subscription IS NULL OR btrim(p_subscription)='' OR p_customer IS NULL OR btrim(p_customer)=''
             OR p_price IS NULL OR btrim(p_price)='' OR p_currency NOT IN ('CAD','USD','EUR','XAF')
             OR p_period_start IS NULL OR p_period_end<=p_period_start OR p_provider_updated_at IS NULL THEN
            RETURN false;
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.subscriptions s
            JOIN public.billing_customers c ON c.id=s.billing_customer_id AND c.organization_id=s.organization_id
            WHERE s.provider='simulated' AND s.provider_subscription_reference=p_subscription
              AND c.provider='simulated' AND c.provider_customer_reference=p_customer
              AND s.currency=p_currency AND s.current_period_start=p_period_start
              AND s.current_period_end=p_period_end AND s.provider_updated_at=p_provider_updated_at
              AND p_price='sim_price_'||replace(s.plan_version_id::text,'-','')
          ) THEN RETURN false; END IF;
          INSERT INTO public.simulated_billing_provider_subscriptions(
            provider_subscription_reference,provider_customer_reference,provider_price_reference,currency,state,
            current_period_start,current_period_end,cancel_at_period_end,provider_updated_at
          ) VALUES(p_subscription,p_customer,p_price,p_currency,'pending_checkout',p_period_start,p_period_end,false,
                   p_provider_updated_at)
          ON CONFLICT (provider_subscription_reference) DO NOTHING;
          RETURN EXISTS (
            SELECT 1 FROM public.simulated_billing_provider_subscriptions p
            WHERE p.provider_subscription_reference=p_subscription
              AND p.provider_customer_reference=p_customer AND p.provider_price_reference=p_price
              AND p.currency=p_currency AND p.provider_updated_at>=p_provider_updated_at
          );
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.record_simulated_billing_webhook_snapshot(p_provider text,p_event_id text)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v public.billing_event_inbox%ROWTYPE; v_payload jsonb;
          v_reference text; v_customer text; v_price text; v_currency text; v_state text;
          v_start timestamptz; v_end timestamptz; v_updated timestamptz; v_cancel boolean;
        BEGIN
          SELECT * INTO v FROM public.billing_event_inbox
          WHERE provider=p_provider AND provider_event_id=p_event_id FOR UPDATE;
          IF NOT FOUND THEN RETURN false; END IF;
          IF p_provider<>'simulated' OR v.normalized_payload->'subscription' IS NULL THEN RETURN true; END IF;
          v_payload:=v.normalized_payload->'subscription';
          v_reference:=v_payload->>'reference'; v_customer:=v_payload->>'customer_reference';
          v_price:=v_payload->>'price_reference'; v_currency:=v_payload->>'currency'; v_state:=v_payload->>'state';
          v_start:=(v_payload->>'current_period_start')::timestamptz;
          v_end:=(v_payload->>'current_period_end')::timestamptz;
          v_updated:=(v_payload->>'updated_at')::timestamptz;
          v_cancel:=(v_payload->>'cancel_at_period_end')::boolean;
          IF v_reference IS NULL OR btrim(v_reference)='' OR v.provider_object_reference<>v_reference
             OR v_customer IS NULL OR btrim(v_customer)='' OR v_price IS NULL OR btrim(v_price)=''
             OR v_currency NOT IN ('CAD','USD','EUR','XAF')
             OR v_state NOT IN ('pending_checkout','active','past_due','grace_period','suspended','canceling','canceled')
             OR v_start IS NULL OR v_end<=v_start OR v_updated IS NULL OR v.provider_created_at<>v_updated
             OR v_cancel IS NULL THEN RETURN false; END IF;
          INSERT INTO public.simulated_billing_provider_subscriptions(
            provider_subscription_reference,provider_customer_reference,provider_price_reference,currency,state,
            current_period_start,current_period_end,cancel_at_period_end,provider_updated_at,source_inbox_id,ambiguous
          ) VALUES(v_reference,v_customer,v_price,v_currency,v_state,v_start,v_end,v_cancel,v_updated,v.id,false)
          ON CONFLICT (provider_subscription_reference) DO UPDATE SET
            provider_customer_reference=CASE WHEN EXCLUDED.provider_updated_at>
              simulated_billing_provider_subscriptions.provider_updated_at THEN EXCLUDED.provider_customer_reference
              ELSE simulated_billing_provider_subscriptions.provider_customer_reference END,
            provider_price_reference=CASE WHEN EXCLUDED.provider_updated_at>
              simulated_billing_provider_subscriptions.provider_updated_at THEN EXCLUDED.provider_price_reference
              ELSE simulated_billing_provider_subscriptions.provider_price_reference END,
            currency=CASE WHEN EXCLUDED.provider_updated_at>simulated_billing_provider_subscriptions.provider_updated_at
              THEN EXCLUDED.currency ELSE simulated_billing_provider_subscriptions.currency END,
            state=CASE WHEN EXCLUDED.provider_updated_at>simulated_billing_provider_subscriptions.provider_updated_at
              THEN EXCLUDED.state ELSE simulated_billing_provider_subscriptions.state END,
            current_period_start=CASE WHEN EXCLUDED.provider_updated_at>
              simulated_billing_provider_subscriptions.provider_updated_at THEN EXCLUDED.current_period_start
              ELSE simulated_billing_provider_subscriptions.current_period_start END,
            current_period_end=CASE WHEN EXCLUDED.provider_updated_at>
              simulated_billing_provider_subscriptions.provider_updated_at THEN EXCLUDED.current_period_end
              ELSE simulated_billing_provider_subscriptions.current_period_end END,
            cancel_at_period_end=CASE WHEN EXCLUDED.provider_updated_at>
              simulated_billing_provider_subscriptions.provider_updated_at THEN EXCLUDED.cancel_at_period_end
              ELSE simulated_billing_provider_subscriptions.cancel_at_period_end END,
            source_inbox_id=CASE WHEN EXCLUDED.provider_updated_at>
              simulated_billing_provider_subscriptions.provider_updated_at THEN EXCLUDED.source_inbox_id
              ELSE simulated_billing_provider_subscriptions.source_inbox_id END,
            ambiguous=CASE
              WHEN EXCLUDED.provider_updated_at>simulated_billing_provider_subscriptions.provider_updated_at THEN false
              WHEN EXCLUDED.provider_updated_at=simulated_billing_provider_subscriptions.provider_updated_at AND
                (EXCLUDED.provider_customer_reference,EXCLUDED.provider_price_reference,EXCLUDED.currency,
                 EXCLUDED.state,EXCLUDED.current_period_start,EXCLUDED.current_period_end,EXCLUDED.cancel_at_period_end)
                IS DISTINCT FROM
                (simulated_billing_provider_subscriptions.provider_customer_reference,
                 simulated_billing_provider_subscriptions.provider_price_reference,
                 simulated_billing_provider_subscriptions.currency,simulated_billing_provider_subscriptions.state,
                 simulated_billing_provider_subscriptions.current_period_start,
                 simulated_billing_provider_subscriptions.current_period_end,
                 simulated_billing_provider_subscriptions.cancel_at_period_end) THEN true
              ELSE simulated_billing_provider_subscriptions.ambiguous END,
            provider_updated_at=GREATEST(EXCLUDED.provider_updated_at,
              simulated_billing_provider_subscriptions.provider_updated_at),
            updated_at=clock_timestamp();
          RETURN true;
        EXCEPTION WHEN invalid_text_representation OR datetime_field_overflow THEN RETURN false;
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.read_simulated_billing_provider_subscription(p_reference text)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v public.simulated_billing_provider_subscriptions%ROWTYPE;
        BEGIN
          IF p_reference IS NULL OR btrim(p_reference)='' THEN
            RETURN jsonb_build_object('status','unresolved');
          END IF;
          SELECT * INTO v FROM public.simulated_billing_provider_subscriptions
          WHERE provider_subscription_reference=p_reference;
          IF NOT FOUND OR v.ambiguous THEN RETURN jsonb_build_object('status','unresolved'); END IF;
          RETURN jsonb_build_object(
            'status','found','subscription_reference',v.provider_subscription_reference,
            'customer_reference',v.provider_customer_reference,'price_reference',v.provider_price_reference,
            'currency',v.currency,'state',v.state,'period_start',v.current_period_start,
            'period_end',v.current_period_end,'cancel_at_period_end',v.cancel_at_period_end,
            'provider_updated_at',v.provider_updated_at
          );
        END $fn$;
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.apply_simulated_billing_reconciliation_correction()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $fn$
        DECLARE v_sub public.subscriptions%ROWTYPE; v_proof public.simulated_billing_provider_subscriptions%ROWTYPE;
          v_inbox public.billing_event_inbox%ROWTYPE; v_customer text; v_expected_price text;
          v_event_id uuid; v_previous_state text; v_cause text; v_request text;
        BEGIN
          IF NEW.difference_code<>'local_stale' OR NEW.subscription_id IS NULL THEN RETURN NEW; END IF;
          SELECT * INTO v_sub FROM public.subscriptions
          WHERE id=NEW.subscription_id AND organization_id=NEW.organization_id FOR UPDATE;
          IF NOT FOUND OR v_sub.provider<>'simulated' THEN RETURN NEW; END IF;
          SELECT * INTO v_proof FROM public.simulated_billing_provider_subscriptions
          WHERE provider_subscription_reference=v_sub.provider_subscription_reference FOR UPDATE;
          IF NOT FOUND OR v_proof.ambiguous OR v_proof.source_inbox_id IS NULL
             OR v_proof.provider_updated_at<=v_sub.provider_updated_at THEN RETURN NEW; END IF;
          SELECT * INTO v_inbox FROM public.billing_event_inbox WHERE id=v_proof.source_inbox_id FOR UPDATE;
          IF NOT FOUND OR v_inbox.provider<>'simulated' OR v_inbox.status NOT IN ('admitted','processed')
             OR v_inbox.provider_object_reference<>v_proof.provider_subscription_reference
             OR v_inbox.provider_created_at<>v_proof.provider_updated_at THEN RETURN NEW; END IF;
          SELECT provider_customer_reference INTO v_customer FROM public.billing_customers
          WHERE id=v_sub.billing_customer_id AND organization_id=v_sub.organization_id AND provider='simulated';
          v_expected_price:='sim_price_'||replace(v_sub.plan_version_id::text,'-','');
          IF v_customer IS DISTINCT FROM v_proof.provider_customer_reference
             OR v_sub.currency IS DISTINCT FROM v_proof.currency
             OR v_expected_price IS DISTINCT FROM v_proof.provider_price_reference
             OR v_proof.current_period_start<v_sub.current_period_start
             OR v_proof.current_period_end<v_sub.current_period_end
             OR v_proof.cancel_at_period_end IS DISTINCT FROM v_sub.cancel_at_period_end THEN RETURN NEW; END IF;
          IF v_inbox.event_type='invoice.paid' AND v_proof.state='active'
             AND v_sub.state IN ('pending_checkout','active','past_due','grace_period','suspended') THEN
            v_cause:='invoice_paid';
          ELSIF v_inbox.event_type='invoice.payment_failed' AND v_proof.state='past_due'
             AND v_sub.state IN ('active','past_due') THEN v_cause:='payment_failed';
          ELSE RETURN NEW; END IF;
          IF (v_inbox.normalized_payload #>> '{subscription,reference}') IS DISTINCT FROM v_proof.provider_subscription_reference
             OR (v_inbox.normalized_payload #>> '{subscription,customer_reference}') IS DISTINCT FROM v_proof.provider_customer_reference
             OR (v_inbox.normalized_payload #>> '{subscription,price_reference}') IS DISTINCT FROM v_proof.provider_price_reference
             OR (v_inbox.normalized_payload #>> '{subscription,currency}') IS DISTINCT FROM v_proof.currency
             OR (v_inbox.normalized_payload #>> '{subscription,state}') IS DISTINCT FROM v_proof.state
             OR ((v_inbox.normalized_payload #>> '{subscription,updated_at}')::timestamptz)
                IS DISTINCT FROM v_proof.provider_updated_at THEN RETURN NEW; END IF;
          v_previous_state:=v_sub.state;
          UPDATE public.subscriptions SET state=v_proof.state,current_period_start=v_proof.current_period_start,
            current_period_end=v_proof.current_period_end,cancel_at_period_end=v_proof.cancel_at_period_end,
            provider_updated_at=v_proof.provider_updated_at,provider_version=provider_version+1,version=version+1,
            updated_at=clock_timestamp(),grace_policy_version=CASE WHEN v_proof.state='active' THEN NULL ELSE grace_policy_version END,
            grace_started_at=CASE WHEN v_proof.state='active' THEN NULL ELSE grace_started_at END,
            grace_ends_at=CASE WHEN v_proof.state='active' THEN NULL ELSE grace_ends_at END WHERE id=v_sub.id;
          SELECT id INTO v_event_id FROM public.billing_events WHERE inbox_id=v_inbox.id;
          IF v_event_id IS NULL THEN
            INSERT INTO public.billing_events(organization_id,inbox_id,subscription_id,provider,provider_event_id,
              event_type,schema_version,normalized_payload,occurred_at)
            VALUES(v_sub.organization_id,v_inbox.id,v_sub.id,v_inbox.provider,v_inbox.provider_event_id,
              v_inbox.event_type,1,v_inbox.normalized_payload,v_inbox.provider_created_at) RETURNING id INTO v_event_id;
          ELSIF NOT EXISTS (
            SELECT 1 FROM public.billing_events e WHERE e.id=v_event_id
              AND e.organization_id=v_sub.organization_id AND e.subscription_id=v_sub.id
              AND e.provider=v_inbox.provider AND e.provider_event_id=v_inbox.provider_event_id
          ) THEN
            RAISE EXCEPTION 'billing_reconciliation_event_scope_mismatch';
          END IF;
          IF v_previous_state<>v_proof.state THEN
            INSERT INTO public.subscription_transitions(organization_id,subscription_id,source_billing_event_id,
              previous_state,next_state,cause,occurred_at)
            VALUES(v_sub.organization_id,v_sub.id,v_event_id,v_previous_state,v_proof.state,v_cause,v_inbox.provider_created_at);
            IF v_proof.state='active' THEN
              UPDATE public.organization_plan_contracts SET state='active',updated_at=clock_timestamp(),version=version+1
              WHERE organization_id=v_sub.organization_id AND plan_version_id=v_sub.plan_version_id
                AND state IN ('pending','suspended');
            END IF;
          END IF;
          UPDATE public.billing_event_inbox SET status='processed',last_error_code=NULL,
            processed_at=coalesce(processed_at,clock_timestamp()),updated_at=clock_timestamp() WHERE id=v_inbox.id;
          NEW.resolved_at:=clock_timestamp();
          v_request:='billing-reconciliation-'||NEW.run_id::text;
          PERFORM set_config('app.organization_id',NEW.organization_id::text,true);
          PERFORM set_config('app.actor_id','',true); PERFORM set_config('app.request_id',v_request,true);
          PERFORM app_private.append_audit_event(gen_random_uuid(),'tenant',NEW.organization_id,'system',NULL,
            'billing.reconciliation_correction_applied','billing_reconciliation_difference',NEW.id,
            v_request,v_request,'worker',jsonb_build_object('difference_code','local_stale',
            'previous_state',v_previous_state,'next_state',v_proof.state),1::smallint);
          RETURN NEW;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_RECORD_CHECKOUT} OWNER TO prospect_rls_definer")
    op.execute(f"ALTER FUNCTION {_RECORD_WEBHOOK} OWNER TO prospect_rls_definer")
    op.execute(f"ALTER FUNCTION {_READ_SNAPSHOT} OWNER TO prospect_rls_definer")
    op.execute(f"ALTER FUNCTION {_APPLY_CORRECTION} OWNER TO prospect_rls_definer")
    for signature in (_RECORD_CHECKOUT, _RECORD_WEBHOOK):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC, prospect_worker")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prospect_app")
    op.execute(f"REVOKE ALL ON FUNCTION {_READ_SNAPSHOT} FROM PUBLIC, prospect_app")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_READ_SNAPSHOT} TO prospect_worker")
    op.execute(f"REVOKE ALL ON FUNCTION {_APPLY_CORRECTION} FROM PUBLIC, prospect_app, prospect_worker")
    op.execute(
        "CREATE TRIGGER trg_apply_simulated_billing_reconciliation_correction "
        "BEFORE INSERT ON public.billing_reconciliation_differences FOR EACH ROW "
        "EXECUTE FUNCTION app_private.apply_simulated_billing_reconciliation_correction()"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $guard$
        BEGIN
          IF EXISTS (SELECT 1 FROM public.simulated_billing_provider_subscriptions) THEN
            RAISE EXCEPTION 'P53-08 rollback blocked: simulated provider evidence exists';
          END IF;
        END $guard$;
        """
    )
    op.execute(
        "DROP TRIGGER trg_apply_simulated_billing_reconciliation_correction "
        "ON public.billing_reconciliation_differences"
    )
    op.execute(f"DROP FUNCTION {_APPLY_CORRECTION}")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_READ_SNAPSHOT} FROM prospect_worker")
    op.execute(f"DROP FUNCTION {_READ_SNAPSHOT}")
    for signature in (_RECORD_WEBHOOK, _RECORD_CHECKOUT):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM prospect_app")
        op.execute(f"DROP FUNCTION {signature}")
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE ON public.simulated_billing_provider_subscriptions FROM prospect_rls_definer"
    )
    op.execute("DROP TABLE public.simulated_billing_provider_subscriptions")
