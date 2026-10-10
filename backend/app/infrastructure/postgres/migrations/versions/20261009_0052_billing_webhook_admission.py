"""Admission durable des webhooks Billing P53-04.

Revision ID: 20261009_0052
Revises: 20261009_0051
Create Date: 2026-10-09
"""

from alembic import op

revision = "20261009_0052"
down_revision = "20261009_0051"
branch_labels = None
depends_on = None

_ADMIT_WEBHOOK_SIGNATURE = (
    "app_private.admit_billing_webhook(text, text, text, text, timestamptz, timestamptz, text, jsonb)"
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.billing_webhook_collisions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          provider varchar(16) NOT NULL,
          provider_event_id varchar(255) NOT NULL,
          existing_payload_digest char(64) NOT NULL,
          conflicting_payload_digest char(64) NOT NULL,
          received_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT ck_billing_webhook_collisions_provider CHECK (provider IN ('simulated','stripe')),
          CONSTRAINT ck_billing_webhook_collisions_references CHECK (
            char_length(btrim(provider_event_id)) BETWEEN 1 AND 255
          ),
          CONSTRAINT ck_billing_webhook_collisions_digests CHECK (
            existing_payload_digest ~ '^[a-f0-9]{64}$'
            AND conflicting_payload_digest ~ '^[a-f0-9]{64}$'
            AND existing_payload_digest <> conflicting_payload_digest
          )
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_billing_webhook_collisions_digest "
        "ON public.billing_webhook_collisions(provider, provider_event_id, conflicting_payload_digest)"
    )
    op.execute("ALTER TABLE public.billing_webhook_collisions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.billing_webhook_collisions FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON public.billing_webhook_collisions FROM PUBLIC, prospect_app, prospect_worker")
    op.execute("GRANT SELECT, INSERT ON public.billing_webhook_collisions TO prospect_rls_definer")
    op.execute(
        r"""
        CREATE FUNCTION app_private.admit_billing_webhook(
          p_provider text, p_provider_event_id text, p_event_type text, p_object_reference text,
          p_provider_created_at timestamptz, p_received_at timestamptz, p_payload_digest text,
          p_normalized_payload jsonb
        ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp AS $fn$
        DECLARE v_existing_digest text;
        BEGIN
          IF p_provider NOT IN ('simulated','stripe')
             OR p_event_type NOT IN ('checkout.completed','subscription.snapshot','invoice.paid','invoice.payment_failed','refund.succeeded')
             OR p_provider_event_id IS NULL OR char_length(btrim(p_provider_event_id)) NOT BETWEEN 1 AND 255
             OR p_object_reference IS NULL OR char_length(btrim(p_object_reference)) NOT BETWEEN 1 AND 255
             OR p_provider_created_at IS NULL OR p_received_at IS NULL
             OR p_payload_digest !~ '^[a-f0-9]{64}$'
             OR jsonb_typeof(p_normalized_payload) <> 'object'
             OR octet_length(p_normalized_payload::text) > 65536 THEN
            RAISE EXCEPTION 'invalid_billing_webhook_admission' USING ERRCODE = '22023';
          END IF;
          INSERT INTO public.billing_event_inbox(
            provider, provider_event_id, event_type, provider_object_reference, provider_created_at, received_at,
            payload_digest, signature_version, api_version, normalized_payload, status, attempt_count, created_at, updated_at
          ) VALUES (
            p_provider, p_provider_event_id, p_event_type, p_object_reference, p_provider_created_at, p_received_at,
            p_payload_digest, 1, 'normalized-v1', p_normalized_payload, 'admitted', 0, p_received_at, p_received_at
          ) ON CONFLICT (provider, provider_event_id) DO NOTHING;
          IF FOUND THEN
            RETURN jsonb_build_object('code', 'admitted');
          END IF;
          SELECT payload_digest INTO v_existing_digest
          FROM public.billing_event_inbox
          WHERE provider = p_provider AND provider_event_id = p_provider_event_id;
          IF v_existing_digest = p_payload_digest THEN
            RETURN jsonb_build_object('code', 'duplicate');
          END IF;
          INSERT INTO public.billing_webhook_collisions(
            provider, provider_event_id, existing_payload_digest, conflicting_payload_digest, received_at
          ) VALUES (
            p_provider, p_provider_event_id, v_existing_digest, p_payload_digest, p_received_at
          ) ON CONFLICT (provider, provider_event_id, conflicting_payload_digest) DO NOTHING;
          RETURN jsonb_build_object('code', 'collision');
        END $fn$;
        """
    )
    op.execute(f"ALTER FUNCTION {_ADMIT_WEBHOOK_SIGNATURE} OWNER TO prospect_rls_definer")
    op.execute(f"REVOKE ALL ON FUNCTION {_ADMIT_WEBHOOK_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_ADMIT_WEBHOOK_SIGNATURE} TO prospect_app")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_ADMIT_WEBHOOK_SIGNATURE} FROM prospect_app")
    op.execute(f"DROP FUNCTION {_ADMIT_WEBHOOK_SIGNATURE}")
    op.execute("REVOKE SELECT, INSERT ON public.billing_webhook_collisions FROM prospect_rls_definer")
    op.execute("DROP INDEX public.uq_billing_webhook_collisions_digest")
    op.execute("DROP TABLE public.billing_webhook_collisions")
