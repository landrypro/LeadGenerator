"""Preuves P53-05 : projection atomique, ordre, reprise et RLS worker."""

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.billing_projection import BillingProjectionWorker

pytestmark = pytest.mark.integration


def _urls() -> tuple[str, str]:
    worker_url = os.environ.get("TEST_WORKER_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not worker_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_WORKER_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("Les URL PostgreSQL worker et proprietaire sont requises.")
    return worker_url, owner_url


def _database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=2,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=10_000,
    )


def _payload(
    *, subscription_reference: str, customer_reference: str, updated_at: datetime, state: str
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "provider_object_reference": subscription_reference,
        "subscription": {
            "reference": subscription_reference,
            "customer_reference": customer_reference,
            "state": state,
            "currency": "CAD",
            "price_reference": "price_simulated",
            "current_period_start": updated_at.isoformat(),
            "current_period_end": (updated_at + timedelta(days=30)).isoformat(),
            "cancel_at_period_end": False,
            "updated_at": updated_at.isoformat(),
        },
    }


async def test_billing_projection_is_atomic_monotone_and_recoverable() -> None:
    worker_url, owner_url = _urls()
    worker, owner = _database(worker_url), _database(owner_url)
    actor, organization, plan, plan_version, customer, subscription = (uuid4() for _ in range(6))
    paid_inbox, stale_inbox, broken_inbox = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    customer_reference = f"customer-{customer}"
    subscription_reference = f"subscription-{subscription}"
    broken_payload = _payload(
        subscription_reference=subscription_reference,
        customer_reference=customer_reference,
        updated_at=now + timedelta(minutes=1),
        state="active",
    )
    subscription_payload = broken_payload["subscription"]
    assert isinstance(subscription_payload, dict)
    subscription_payload["current_period_start"] = "invalid-time"
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO users (id,email,email_normalized,display_name,password_hash,status,created_at,updated_at)
                    VALUES (:actor,:email,:email,'Projection','hash','active',:now,:now);
                    INSERT INTO organizations (id,name,timezone,status,created_by,activated_at,created_at,updated_at)
                    VALUES (:organization,'Projection','America/Toronto','active',:actor,:now,:now,:now);
                    INSERT INTO plan_catalog (id,code,state) VALUES (:plan,'custom','draft');
                    INSERT INTO plan_versions (
                      id,plan_id,version_number,state,currency,billing_cycle,amount_excluding_tax_minor,
                      effective_from,created_by_user_id,approved_by_user_id,published_at
                    ) VALUES (:plan_version,:plan,1,'published','CAD','monthly',0,:now,:actor,:actor,:now);
                    INSERT INTO billing_customers (id,organization_id,provider,provider_customer_reference)
                    VALUES (:customer,:organization,'simulated',:customer_reference);
                    INSERT INTO subscriptions (
                      id,organization_id,billing_customer_id,provider,provider_subscription_reference,plan_version_id,
                      currency,state,current_period_start,current_period_end,provider_updated_at
                    ) VALUES (
                      :subscription,:organization,:customer,'simulated',:subscription_reference,:plan_version,
                      'CAD','pending_checkout',:previous,:now,:previous
                    );
                    """
                ),
                {
                    "actor": actor,
                    "email": f"projection-{actor}@example.test",
                    "organization": organization,
                    "plan": plan,
                    "plan_version": plan_version,
                    "customer": customer,
                    "customer_reference": customer_reference,
                    "subscription": subscription,
                    "subscription_reference": subscription_reference,
                    "now": now,
                    "previous": now - timedelta(minutes=1),
                },
            )
            for inbox_id, event_id, event_type, created_at, payload, attempts in (
                (
                    paid_inbox,
                    "evt-paid",
                    "invoice.paid",
                    now,
                    _payload(
                        subscription_reference=subscription_reference,
                        customer_reference=customer_reference,
                        updated_at=now,
                        state="active",
                    ),
                    0,
                ),
                (
                    stale_inbox,
                    "evt-stale",
                    "invoice.payment_failed",
                    now - timedelta(minutes=10),
                    _payload(
                        subscription_reference=subscription_reference,
                        customer_reference=customer_reference,
                        updated_at=now - timedelta(minutes=10),
                        state="past_due",
                    ),
                    0,
                ),
                (
                    broken_inbox,
                    "evt-broken",
                    "invoice.paid",
                    now + timedelta(minutes=1),
                    broken_payload,
                    7,
                ),
            ):
                await connection.execute(
                    text(
                        """
                        INSERT INTO billing_event_inbox (
                          id,provider,provider_event_id,event_type,provider_object_reference,provider_created_at,
                          received_at,payload_digest,signature_version,api_version,normalized_payload,status,attempt_count
                        ) VALUES (
                          :id,'simulated',:event_id,:event_type,:object_reference,:created_at,
                          :created_at,:digest,1,'normalized-v1',CAST(:payload AS jsonb),'admitted',:attempts
                        )
                        """
                    ),
                    {
                        "id": inbox_id,
                        "event_id": event_id,
                        "event_type": event_type,
                        "object_reference": subscription_reference,
                        "created_at": created_at,
                        "digest": ("a" if inbox_id == paid_inbox else "b" if inbox_id == stale_inbox else "c") * 64,
                        "payload": json.dumps(payload, separators=(",", ":")),
                        "attempts": attempts,
                    },
                )

        async with worker.engine.connect() as connection:
            direct_inbox_read = await connection.scalar(
                text("SELECT has_table_privilege(current_user, 'public.billing_event_inbox', 'SELECT')")
            )
            claim_granted = await connection.scalar(
                text("SELECT has_function_privilege(current_user, 'app_private.claim_billing_event()', 'EXECUTE')")
            )
        assert direct_inbox_read is False
        assert claim_granted is True

        first, second = BillingProjectionWorker(worker.session_factory), BillingProjectionWorker(worker.session_factory)
        claimed = await asyncio.gather(first.run_once(), second.run_once())
        assert claimed.count(True) == 2
        # A fresh instance represents a process restart: it resumes the
        # durable claim/retry state without a second subscription effect.
        restarted = BillingProjectionWorker(worker.session_factory)
        assert await restarted.run_once() is True

        async with owner.engine.connect() as connection:
            state = await connection.scalar(text("SELECT state FROM subscriptions WHERE id=:id"), {"id": subscription})
            events = await connection.scalar(
                text("SELECT count(*) FROM billing_events WHERE inbox_id=:id"), {"id": paid_inbox}
            )
            transitions = await connection.scalar(
                text("SELECT count(*) FROM subscription_transitions WHERE subscription_id=:id"), {"id": subscription}
            )
            audit = await connection.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE entity_id=:id AND action='billing.subscription_transition_applied'"
                ),
                {"id": subscription},
            )
            inbox = (
                (
                    await connection.execute(
                        text(
                            "SELECT id,status,last_error_code FROM billing_event_inbox WHERE id IN (:paid,:stale,:broken) ORDER BY id"
                        ),
                        {"paid": paid_inbox, "stale": stale_inbox, "broken": broken_inbox},
                    )
                )
                .mappings()
                .all()
            )

        by_id = {row["id"]: row for row in inbox}
        assert state == "active"
        assert events == 1 and transitions == 1 and audit == 1
        assert by_id[paid_inbox]["status"] == "processed"
        assert by_id[stale_inbox]["status"] == "ignored"
        assert by_id[stale_inbox]["last_error_code"] == "billing_event_stale"
        assert by_id[broken_inbox]["status"] == "dead_letter"
        assert by_id[broken_inbox]["last_error_code"] == "projection_attempts_exhausted"
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(text("DELETE FROM audit_events WHERE entity_id=:id"), {"id": subscription})
            await connection.execute(
                text("DELETE FROM subscription_transitions WHERE subscription_id=:id"), {"id": subscription}
            )
            await connection.execute(
                text("DELETE FROM billing_events WHERE inbox_id IN (:paid,:stale,:broken)"),
                {"paid": paid_inbox, "stale": stale_inbox, "broken": broken_inbox},
            )
            await connection.execute(
                text("DELETE FROM billing_event_inbox WHERE id IN (:paid,:stale,:broken)"),
                {"paid": paid_inbox, "stale": stale_inbox, "broken": broken_inbox},
            )
            await connection.execute(text("DELETE FROM subscriptions WHERE id=:id"), {"id": subscription})
            await connection.execute(text("DELETE FROM billing_customers WHERE id=:id"), {"id": customer})
            await connection.execute(
                text("UPDATE plan_versions SET state='superseded' WHERE id=:id"), {"id": plan_version}
            )
            await connection.execute(text("DELETE FROM plan_versions WHERE id=:id"), {"id": plan_version})
            await connection.execute(text("DELETE FROM plan_catalog WHERE id=:id"), {"id": plan})
            await connection.execute(text("DELETE FROM organizations WHERE id=:id"), {"id": organization})
            await connection.execute(text("DELETE FROM users WHERE id=:id"), {"id": actor})
        await worker.close()
        await owner.close()
