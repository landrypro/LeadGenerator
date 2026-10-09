"""Add the additive, tenant-safe billing persistence foundation for P53-02.

Revision ID: 20261009_0051
Revises: 20261008_0050
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261009_0051"
down_revision: str | Sequence[str] | None = "20261008_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TENANT_TABLES = (
    "billing_customers",
    "subscriptions",
    "subscription_transitions",
    "billing_commands",
    "billing_events",
    "billing_reconciliation_runs",
    "billing_reconciliation_differences",
    "billing_refunds",
)
_RESERVE_COMMAND_SIGNATURE = "app_private.reserve_billing_command(uuid,text,text,text,timestamp with time zone)"
_SUBSCRIPTION_GUARD_SIGNATURE = "app_private.guard_billing_subscription_scope()"
_RECONCILIATION_GUARD_SIGNATURE = "app_private.guard_billing_reconciliation_difference_scope()"


def upgrade() -> None:
    # A customer reference is opaque.  No email, address, card data, URL or raw
    # provider payload is accepted by this schema.
    op.execute(
        """
        CREATE TABLE public.billing_customers (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          provider varchar(16) NOT NULL,
          provider_customer_reference varchar(255) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          version integer NOT NULL DEFAULT 1,
          CONSTRAINT uq_billing_customers_org_id UNIQUE (organization_id, id),
          CONSTRAINT uq_billing_customers_org_provider UNIQUE (organization_id, provider),
          CONSTRAINT uq_billing_customers_provider_reference UNIQUE (provider, provider_customer_reference),
          CONSTRAINT ck_billing_customers_provider CHECK (provider IN ('simulated','stripe')),
          CONSTRAINT ck_billing_customers_reference_nonempty CHECK (char_length(btrim(provider_customer_reference)) BETWEEN 1 AND 255),
          CONSTRAINT ck_billing_customers_version_positive CHECK (version > 0)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.billing_commands (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          command_kind varchar(16) NOT NULL,
          idempotency_key_digest char(64) NOT NULL,
          request_fingerprint char(64) NOT NULL,
          status varchar(16) NOT NULL DEFAULT 'reserved',
          provider_command_reference varchar(255) NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          version integer NOT NULL DEFAULT 1,
          CONSTRAINT uq_billing_commands_org_id UNIQUE (organization_id, id),
          CONSTRAINT uq_billing_commands_org_key UNIQUE (organization_id, idempotency_key_digest),
          CONSTRAINT ck_billing_commands_kind CHECK (command_kind IN ('checkout','portal','refund')),
          CONSTRAINT ck_billing_commands_key_digest CHECK (idempotency_key_digest ~ '^[a-f0-9]{64}$'),
          CONSTRAINT ck_billing_commands_fingerprint CHECK (request_fingerprint ~ '^[a-f0-9]{64}$'),
          CONSTRAINT ck_billing_commands_status CHECK (status IN ('reserved','succeeded','unknown','failed')),
          CONSTRAINT ck_billing_commands_provider_reference CHECK (
            provider_command_reference IS NULL OR char_length(btrim(provider_command_reference)) BETWEEN 1 AND 255
          ),
          CONSTRAINT ck_billing_commands_version_positive CHECK (version > 0)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.billing_event_inbox (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          provider varchar(16) NOT NULL,
          provider_event_id varchar(255) NOT NULL,
          event_type varchar(48) NOT NULL,
          provider_object_reference varchar(255) NOT NULL,
          provider_created_at timestamptz NOT NULL,
          received_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          payload_digest char(64) NOT NULL,
          signature_version smallint NOT NULL DEFAULT 1,
          api_version varchar(64) NULL,
          normalized_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
          status varchar(16) NOT NULL DEFAULT 'admitted',
          attempt_count smallint NOT NULL DEFAULT 0,
          next_attempt_at timestamptz NULL,
          last_error_code varchar(64) NULL,
          processing_started_at timestamptz NULL,
          processed_at timestamptz NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT uq_billing_event_inbox_provider_event UNIQUE (provider, provider_event_id),
          CONSTRAINT ck_billing_event_inbox_provider CHECK (provider IN ('simulated','stripe')),
          CONSTRAINT ck_billing_event_inbox_type CHECK (event_type IN (
            'checkout.completed','subscription.snapshot','invoice.paid','invoice.payment_failed','refund.succeeded'
          )),
          CONSTRAINT ck_billing_event_inbox_references_nonempty CHECK (
            char_length(btrim(provider_event_id)) BETWEEN 1 AND 255
            AND char_length(btrim(provider_object_reference)) BETWEEN 1 AND 255
          ),
          CONSTRAINT ck_billing_event_inbox_digest CHECK (payload_digest ~ '^[a-f0-9]{64}$'),
          CONSTRAINT ck_billing_event_inbox_signature_version CHECK (signature_version > 0),
          CONSTRAINT ck_billing_event_inbox_payload_object CHECK (jsonb_typeof(normalized_payload) = 'object'),
          CONSTRAINT ck_billing_event_inbox_payload_bounded CHECK (octet_length(normalized_payload::text) <= 65536),
          CONSTRAINT ck_billing_event_inbox_status CHECK (status IN ('admitted','processing','processed','dead_letter','ignored')),
          CONSTRAINT ck_billing_event_inbox_attempts CHECK (attempt_count BETWEEN 0 AND 8)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.subscriptions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          billing_customer_id uuid NOT NULL,
          provider varchar(16) NOT NULL,
          provider_subscription_reference varchar(255) NOT NULL,
          plan_version_id uuid NOT NULL REFERENCES public.plan_versions(id) ON DELETE RESTRICT,
          currency varchar(3) NOT NULL,
          state varchar(24) NOT NULL DEFAULT 'pending_checkout',
          current_period_start timestamptz NOT NULL,
          current_period_end timestamptz NOT NULL,
          cancel_at_period_end boolean NOT NULL DEFAULT false,
          provider_updated_at timestamptz NOT NULL,
          provider_version bigint NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          version integer NOT NULL DEFAULT 1,
          CONSTRAINT uq_subscriptions_org_id UNIQUE (organization_id, id),
          CONSTRAINT uq_subscriptions_provider_reference UNIQUE (provider, provider_subscription_reference),
          CONSTRAINT fk_subscriptions_organization_customer FOREIGN KEY (organization_id, billing_customer_id)
            REFERENCES public.billing_customers(organization_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_subscriptions_provider CHECK (provider IN ('simulated','stripe')),
          CONSTRAINT ck_subscriptions_reference_nonempty CHECK (char_length(btrim(provider_subscription_reference)) BETWEEN 1 AND 255),
          CONSTRAINT ck_subscriptions_currency CHECK (currency IN ('CAD','USD','EUR','XAF')),
          CONSTRAINT ck_subscriptions_state CHECK (state IN (
            'pending_checkout','active','past_due','grace_period','suspended','canceling','canceled'
          )),
          CONSTRAINT ck_subscriptions_period CHECK (current_period_end > current_period_start),
          CONSTRAINT ck_subscriptions_provider_version_positive CHECK (provider_version > 0),
          CONSTRAINT ck_subscriptions_version_positive CHECK (version > 0)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_subscriptions_current_org ON public.subscriptions(organization_id) "
        "WHERE state IN ('pending_checkout','active','past_due','grace_period','suspended','canceling')"
    )
    op.execute(
        "CREATE INDEX ix_subscriptions_org_state ON public.subscriptions(organization_id, state, current_period_end)"
    )
    op.execute(
        """
        CREATE TABLE public.billing_events (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          inbox_id uuid NOT NULL REFERENCES public.billing_event_inbox(id) ON DELETE RESTRICT,
          subscription_id uuid NULL,
          provider varchar(16) NOT NULL,
          provider_event_id varchar(255) NOT NULL,
          event_type varchar(48) NOT NULL,
          schema_version smallint NOT NULL DEFAULT 1,
          normalized_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
          occurred_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT uq_billing_events_org_id UNIQUE (organization_id, id),
          CONSTRAINT uq_billing_events_inbox UNIQUE (inbox_id),
          CONSTRAINT fk_billing_events_organization_subscription FOREIGN KEY (organization_id, subscription_id)
            REFERENCES public.subscriptions(organization_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_billing_events_provider CHECK (provider IN ('simulated','stripe')),
          CONSTRAINT ck_billing_events_type CHECK (event_type IN (
            'checkout.completed','subscription.snapshot','invoice.paid','invoice.payment_failed','refund.succeeded'
          )),
          CONSTRAINT ck_billing_events_reference_nonempty CHECK (char_length(btrim(provider_event_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_billing_events_schema_version CHECK (schema_version > 0),
          CONSTRAINT ck_billing_events_payload_object CHECK (jsonb_typeof(normalized_payload) = 'object'),
          CONSTRAINT ck_billing_events_payload_bounded CHECK (octet_length(normalized_payload::text) <= 65536)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_billing_events_org_occurred ON public.billing_events(organization_id, occurred_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE public.subscription_transitions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          subscription_id uuid NOT NULL,
          source_billing_event_id uuid NULL,
          previous_state varchar(24) NOT NULL,
          next_state varchar(24) NOT NULL,
          cause varchar(32) NOT NULL,
          occurred_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT fk_subscription_transitions_organization_subscription FOREIGN KEY (organization_id, subscription_id)
            REFERENCES public.subscriptions(organization_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_subscription_transitions_organization_event FOREIGN KEY (organization_id, source_billing_event_id)
            REFERENCES public.billing_events(organization_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_subscription_transitions_previous_state CHECK (previous_state IN (
            'pending_checkout','active','past_due','grace_period','suspended','canceling','canceled'
          )),
          CONSTRAINT ck_subscription_transitions_next_state CHECK (next_state IN (
            'pending_checkout','active','past_due','grace_period','suspended','canceling','canceled'
          )),
          CONSTRAINT ck_subscription_transitions_distinct_states CHECK (previous_state <> next_state),
          CONSTRAINT ck_subscription_transitions_cause CHECK (cause IN (
            'invoice_paid','checkout_abandoned','payment_failed','grace_period_started','grace_period_expired',
            'cancellation_scheduled','cancellation_revoked','cancellation_confirmed','new_checkout'
          ))
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_subscription_transitions_org_subscription ON public.subscription_transitions(organization_id, subscription_id, occurred_at)"
    )
    op.execute(
        """
        CREATE TABLE public.billing_reconciliation_runs (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          run_kind varchar(16) NOT NULL,
          status varchar(16) NOT NULL DEFAULT 'pending',
          cursor_reference varchar(255) NULL,
          window_started_at timestamptz NOT NULL,
          window_ended_at timestamptz NOT NULL,
          started_at timestamptz NULL,
          completed_at timestamptz NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT uq_billing_reconciliation_runs_org_id UNIQUE (organization_id, id),
          CONSTRAINT ck_billing_reconciliation_runs_kind CHECK (run_kind IN ('incremental','exhaustive','manual')),
          CONSTRAINT ck_billing_reconciliation_runs_status CHECK (status IN ('pending','running','completed','failed','blocked')),
          CONSTRAINT ck_billing_reconciliation_runs_window CHECK (window_ended_at > window_started_at),
          CONSTRAINT ck_billing_reconciliation_runs_completion CHECK (completed_at IS NULL OR started_at IS NOT NULL)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.billing_reconciliation_differences (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          run_id uuid NOT NULL REFERENCES public.billing_reconciliation_runs(id) ON DELETE RESTRICT,
          subscription_id uuid NULL,
          difference_code varchar(24) NOT NULL,
          local_reference varchar(255) NULL,
          provider_reference varchar(255) NULL,
          resolved_at timestamptz NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT fk_billing_reconciliation_differences_organization_subscription
            FOREIGN KEY (organization_id, subscription_id)
            REFERENCES public.subscriptions(organization_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_billing_reconciliation_differences_code CHECK (difference_code IN (
            'in_sync','local_stale','provider_stale','mapping_missing','currency_mismatch','price_mismatch','unresolved'
          )),
          CONSTRAINT ck_billing_reconciliation_differences_references CHECK (
            (local_reference IS NULL OR char_length(btrim(local_reference)) BETWEEN 1 AND 255)
            AND (provider_reference IS NULL OR char_length(btrim(provider_reference)) BETWEEN 1 AND 255)
          )
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_billing_reconciliation_differences_org_run ON public.billing_reconciliation_differences(organization_id, run_id)"
    )
    op.execute(
        """
        CREATE TABLE public.billing_refunds (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE RESTRICT,
          subscription_id uuid NOT NULL,
          billing_command_id uuid NOT NULL,
          provider_payment_reference varchar(255) NOT NULL,
          provider_refund_reference varchar(255) NULL,
          state varchar(16) NOT NULL DEFAULT 'requested',
          requested_at timestamptz NOT NULL,
          decided_at timestamptz NULL,
          completed_at timestamptz NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          version integer NOT NULL DEFAULT 1,
          CONSTRAINT uq_billing_refunds_command UNIQUE (billing_command_id),
          CONSTRAINT fk_billing_refunds_organization_subscription FOREIGN KEY (organization_id, subscription_id)
            REFERENCES public.subscriptions(organization_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_billing_refunds_organization_command FOREIGN KEY (organization_id, billing_command_id)
            REFERENCES public.billing_commands(organization_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_billing_refunds_payment_reference CHECK (char_length(btrim(provider_payment_reference)) BETWEEN 1 AND 255),
          CONSTRAINT ck_billing_refunds_refund_reference CHECK (
            provider_refund_reference IS NULL OR char_length(btrim(provider_refund_reference)) BETWEEN 1 AND 255
          ),
          CONSTRAINT ck_billing_refunds_state CHECK (state IN ('requested','approved','rejected','succeeded','failed')),
          CONSTRAINT ck_billing_refunds_decision CHECK (decided_at IS NULL OR decided_at >= requested_at),
          CONSTRAINT ck_billing_refunds_completion CHECK (completed_at IS NULL OR decided_at IS NOT NULL),
          CONSTRAINT ck_billing_refunds_version_positive CHECK (version > 0)
        )
        """
    )

    op.execute(
        r"""
        CREATE FUNCTION app_private.guard_billing_subscription_scope()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_plan_currency text;
          v_customer public.billing_customers%ROWTYPE;
        BEGIN
          SELECT currency INTO v_plan_currency FROM public.plan_versions WHERE id = NEW.plan_version_id;
          IF NOT FOUND OR v_plan_currency <> NEW.currency THEN
            RAISE EXCEPTION 'billing_subscription_currency_mismatch' USING ERRCODE = '23514';
          END IF;
          SELECT * INTO v_customer FROM public.billing_customers
          WHERE organization_id = NEW.organization_id AND id = NEW.billing_customer_id;
          IF NOT FOUND OR v_customer.provider <> NEW.provider THEN
            RAISE EXCEPTION 'billing_subscription_customer_scope_mismatch' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_SUBSCRIPTION_GUARD_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_SUBSCRIPTION_GUARD_SIGNATURE} FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER trg_subscriptions_scope BEFORE INSERT OR UPDATE ON public.subscriptions "
        "FOR EACH ROW EXECUTE FUNCTION app_private.guard_billing_subscription_scope()"
    )
    op.execute(
        r"""
        CREATE FUNCTION app_private.guard_billing_reconciliation_difference_scope()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_run_organization_id uuid;
        BEGIN
          SELECT organization_id INTO v_run_organization_id
          FROM public.billing_reconciliation_runs WHERE id = NEW.run_id;
          IF NOT FOUND OR (v_run_organization_id IS NOT NULL AND v_run_organization_id <> NEW.organization_id) THEN
            RAISE EXCEPTION 'billing_reconciliation_scope_mismatch' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_RECONCILIATION_GUARD_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_RECONCILIATION_GUARD_SIGNATURE} FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER trg_billing_reconciliation_differences_scope "
        "BEFORE INSERT OR UPDATE ON public.billing_reconciliation_differences "
        "FOR EACH ROW EXECUTE FUNCTION app_private.guard_billing_reconciliation_difference_scope()"
    )

    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_read ON public.{table} FOR SELECT TO prospect_app "
            "USING (organization_id = app_private.current_organization_id())"
        )
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC, prospect_app, prospect_worker")
    op.execute("GRANT SELECT ON public.subscriptions TO prospect_app")

    # The inbox is platform-scoped.  The web role, including a tenant-bound
    # request, cannot inspect or mutate it directly.
    op.execute("ALTER TABLE public.billing_event_inbox ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.billing_event_inbox FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON public.billing_event_inbox FROM PUBLIC, prospect_app, prospect_worker")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON public.billing_customers, public.subscriptions, "
        "public.subscription_transitions, public.billing_commands, public.billing_event_inbox, public.billing_events, "
        "public.billing_reconciliation_runs, public.billing_reconciliation_differences, public.billing_refunds "
        "TO prospect_rls_definer"
    )

    op.execute(
        r"""
        CREATE FUNCTION app_private.reserve_billing_command(
          p_id uuid, p_command_kind text, p_idempotency_key_digest text,
          p_request_fingerprint text, p_now timestamptz
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE
          v_organization_id uuid := app_private.current_organization_id();
          v_existing public.billing_commands%ROWTYPE;
        BEGIN
          IF v_organization_id IS NULL OR p_id IS NULL OR p_now IS NULL
            OR p_command_kind NOT IN ('checkout','portal','refund')
            OR p_idempotency_key_digest !~ '^[a-f0-9]{64}$'
            OR p_request_fingerprint !~ '^[a-f0-9]{64}$' THEN
            RAISE EXCEPTION 'invalid_billing_command' USING ERRCODE = '22023';
          END IF;
          INSERT INTO public.billing_commands(
            id, organization_id, command_kind, idempotency_key_digest, request_fingerprint, status, created_at, updated_at
          ) VALUES (
            p_id, v_organization_id, p_command_kind, p_idempotency_key_digest, p_request_fingerprint,
            'reserved', p_now, p_now
          ) ON CONFLICT (organization_id, idempotency_key_digest) DO NOTHING;
          IF FOUND THEN
            RETURN jsonb_build_object('code','reserved','command_id',p_id,'status','reserved');
          END IF;
          SELECT * INTO v_existing FROM public.billing_commands
          WHERE organization_id = v_organization_id AND idempotency_key_digest = p_idempotency_key_digest
          FOR UPDATE;
          IF v_existing.command_kind <> p_command_kind OR v_existing.request_fingerprint <> p_request_fingerprint THEN
            RETURN jsonb_build_object('code','conflict');
          END IF;
          RETURN jsonb_build_object('code','replayed','command_id',v_existing.id,'status',v_existing.status);
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_RESERVE_COMMAND_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_RESERVE_COMMAND_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_RESERVE_COMMAND_SIGNATURE} TO prospect_app")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_RESERVE_COMMAND_SIGNATURE} FROM prospect_app")
    op.execute(f"DROP FUNCTION {_RESERVE_COMMAND_SIGNATURE}")
    op.execute("DROP TRIGGER trg_billing_reconciliation_differences_scope ON public.billing_reconciliation_differences")
    op.execute(f"DROP FUNCTION {_RECONCILIATION_GUARD_SIGNATURE}")
    op.execute("DROP TRIGGER trg_subscriptions_scope ON public.subscriptions")
    op.execute(f"DROP FUNCTION {_SUBSCRIPTION_GUARD_SIGNATURE}")
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON public.billing_customers, public.subscriptions, "
        "public.subscription_transitions, public.billing_commands, public.billing_event_inbox, public.billing_events, "
        "public.billing_reconciliation_runs, public.billing_reconciliation_differences, public.billing_refunds "
        "FROM prospect_rls_definer"
    )
    for table in _TENANT_TABLES:
        op.execute(f"DROP POLICY {table}_tenant_read ON public.{table}")
    op.execute("DROP TABLE public.billing_refunds")
    op.execute("DROP TABLE public.billing_reconciliation_differences")
    op.execute("DROP TABLE public.billing_reconciliation_runs")
    op.execute("DROP TABLE public.subscription_transitions")
    op.execute("DROP TABLE public.billing_events")
    op.execute("DROP TABLE public.subscriptions")
    op.execute("DROP TABLE public.billing_event_inbox")
    op.execute("DROP TABLE public.billing_commands")
    op.execute("DROP TABLE public.billing_customers")
