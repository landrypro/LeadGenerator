"""DEV-01: a paid invoice, rather than Checkout return, grants sandbox access."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from backend.app.infrastructure.postgres import PostgresDatabase

pytestmark = pytest.mark.integration


async def test_stripe_projection_requires_payment_and_rejects_stale_or_cross_customer() -> None:
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    if not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_MIGRATION_DATABASE_URL is required")
        pytest.skip("TEST_MIGRATION_DATABASE_URL is required")
    database = PostgresDatabase(
        owner_url,
        connect_timeout_seconds=2,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=10_000,
    )
    actor, approver, organization, plan, version, customer, command, checkout = (uuid4() for _ in range(8))
    now = datetime.now(UTC).replace(microsecond=0)
    period_start, period_end = now - timedelta(days=1), now + timedelta(days=29)
    try:
        async with database.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text("""
                        INSERT INTO users(id,email,email_normalized,display_name,password_hash,status)
                        VALUES (:actor,:email,:email,'Stripe creator','hash','active'),
                               (:approver,:other,:other,'Stripe approver','hash','active')
                    """),
                    {
                        "actor": actor,
                        "email": f"stripe-{actor}@example.test",
                        "approver": approver,
                        "other": f"stripe-{approver}@example.test",
                    },
                )
                await connection.execute(
                    text("""
                        INSERT INTO organizations(id,name,timezone,status,created_by,activated_at)
                        VALUES (:id,'Stripe DEV-01','America/Toronto','active',:actor,:now)
                    """),
                    {"id": organization, "actor": actor, "now": now},
                )
                await connection.execute(
                    text("INSERT INTO plan_catalog(id,code,state) VALUES (:id,'custom','published')"),
                    {"id": plan},
                )
                await connection.execute(
                    text("""
                        INSERT INTO plan_versions(id,plan_id,version_number,state,currency,billing_cycle,
                          amount_excluding_tax_minor,effective_from,created_by_user_id,approved_by_user_id,published_at)
                        VALUES (:id,:plan,1,'published','XAF','monthly',5000,:now,:actor,:approver,:now)
                    """),
                    {"id": version, "plan": plan, "now": now, "actor": actor, "approver": approver},
                )
                await connection.execute(
                    text("""
                        INSERT INTO organization_plan_contracts(organization_id,plan_version_id,state,currency,
                          effective_from,created_by_user_id,updated_by_user_id)
                        VALUES (:org,:version,'pending','XAF',:now,:actor,:actor)
                    """),
                    {"org": organization, "version": version, "now": now, "actor": actor},
                )
                await connection.execute(
                    text("""
                        INSERT INTO billing_customers(id,organization_id,provider,provider_customer_reference)
                        VALUES (:id,:org,'stripe','cus_dev01')
                    """),
                    {"id": customer, "org": organization},
                )
                await connection.execute(
                    text("""
                        INSERT INTO billing_commands(id,organization_id,command_kind,idempotency_key_digest,
                          request_fingerprint,status,provider_command_reference)
                        VALUES (:id,:org,'checkout',:key,:fingerprint,'succeeded','cs_test_dev01')
                    """),
                    {"id": command, "org": organization, "key": "a" * 64, "fingerprint": "b" * 64},
                )
                await connection.execute(
                    text("""
                        INSERT INTO stripe_sandbox_checkout_sessions(id,organization_id,billing_command_id,
                          billing_customer_id,plan_version_id,provider_checkout_reference,
                          provider_price_reference,currency,expires_at)
                        VALUES (:id,:org,:command,:customer,:version,'cs_test_dev01','price_dev01','XAF',:expires)
                    """),
                    {
                        "id": checkout,
                        "org": organization,
                        "command": command,
                        "customer": customer,
                        "version": version,
                        "expires": now + timedelta(days=1),
                    },
                )

                async def project(event_type: str, evidence: dict, observed: datetime) -> dict:
                    inbox = uuid4()
                    await connection.execute(
                        text("""
                            INSERT INTO billing_event_inbox(id,provider,provider_event_id,event_type,
                              provider_object_reference,provider_created_at,payload_digest,normalized_payload,
                              status,attempt_count,processing_started_at)
                            VALUES (:id,'stripe',:event,:kind,'sub_dev01',:now,:digest,'{}','processing',1,:now)
                        """),
                        {"id": inbox, "event": f"evt_{inbox.hex}", "kind": event_type, "now": now, "digest": "c" * 64},
                    )
                    evidence["observed_at"] = observed.isoformat()
                    return await connection.scalar(
                        text("SELECT app_private.project_stripe_sandbox_event(:id,1,CAST(:evidence AS jsonb))"),
                        {"id": inbox, "evidence": json.dumps(evidence)},
                    )

                def proof(*, paid: bool, status: str = "active", customer_ref: str = "cus_dev01") -> dict:
                    return {
                        "checkout_command_id": str(command),
                        "subscription": {
                            "reference": "sub_dev01",
                            "customer_reference": customer_ref,
                            "price_reference": "price_dev01",
                            "currency": "XAF",
                            "provider_status": status,
                            "current_period_start": period_start.isoformat(),
                            "current_period_end": period_end.isoformat(),
                            "cancel_at_period_end": False,
                        },
                        "invoice": {
                            "amount_minor": 5000,
                            "paid": paid,
                            "period_start": period_start.isoformat(),
                            "period_end": period_end.isoformat(),
                        },
                    }

                first_observation = datetime.now(UTC)
                assert (await project("checkout.completed", proof(paid=False), first_observation))[
                    "result_code"
                ] == "processed"
                assert (
                    await connection.scalar(
                        text("SELECT state FROM organization_plan_contracts WHERE organization_id=:org"),
                        {"org": organization},
                    )
                    == "pending"
                )

                paid_observation = datetime.now(UTC)
                assert (await project("invoice.paid", proof(paid=True), paid_observation))["result_code"] == "processed"
                assert (
                    await connection.scalar(
                        text("SELECT state FROM organization_plan_contracts WHERE organization_id=:org"),
                        {"org": organization},
                    )
                    == "active"
                )
                assert (await project("invoice.payment_failed", proof(paid=False), now - timedelta(minutes=1)))[
                    "result_code"
                ] == "ignored"
                assert (
                    await connection.scalar(
                        text("SELECT state FROM subscriptions WHERE provider_subscription_reference='sub_dev01'"),
                    )
                    == "active"
                )

                period_start, period_end = period_end, period_end + timedelta(days=30)
                assert (
                    await project("invoice.payment_failed", proof(paid=False, status="past_due"), datetime.now(UTC))
                )["result_code"] == "processed"
                assert (
                    await connection.scalar(
                        text("SELECT state FROM subscriptions WHERE provider_subscription_reference='sub_dev01'"),
                    )
                    == "grace_period"
                )
                assert (
                    await connection.scalar(
                        text("SELECT state FROM organization_plan_contracts WHERE organization_id=:org"),
                        {"org": organization},
                    )
                    == "active"
                )
                assert (await project("invoice.paid", proof(paid=True), datetime.now(UTC)))[
                    "result_code"
                ] == "processed"
                assert (
                    await connection.scalar(
                        text("SELECT state FROM subscriptions WHERE provider_subscription_reference='sub_dev01'"),
                    )
                    == "active"
                )

                nested = await connection.begin_nested()
                with pytest.raises(Exception, match="stripe_mapping_incompatible"):
                    await project("invoice.paid", proof(paid=True, customer_ref="cus_other"), datetime.now(UTC))
                await nested.rollback()
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM billing_events WHERE provider='stripe'"),
                    )
                    == 4
                )

                retry_id = uuid4()
                retry_payload = {"schema_version": 1, "provider_object_reference": "sub_dev01"}
                await connection.execute(
                    text("""
                        INSERT INTO billing_event_inbox(id,provider,provider_event_id,event_type,
                          provider_object_reference,provider_created_at,payload_digest,normalized_payload,
                          status,attempt_count,last_error_code)
                        VALUES (:id,'stripe',:event,'subscription.snapshot','sub_dev01',:now,:digest,
                          CAST(:payload AS jsonb),'dead_letter',8,'projection_attempts_exhausted')
                    """),
                    {
                        "id": retry_id,
                        "event": f"evt_{retry_id.hex}",
                        "now": now,
                        "digest": "d" * 64,
                        "payload": json.dumps(retry_payload),
                    },
                )
                assert (
                    await connection.scalar(
                        text("""
                        SELECT app_private.admit_stripe_sync_event(:event,'subscription.snapshot',
                          'sub_dev01',:now,CAST(:payload AS jsonb))
                    """),
                        {"event": f"evt_{retry_id.hex}", "now": now, "payload": json.dumps(retry_payload)},
                    )
                    is True
                )
                assert (
                    await connection.scalar(
                        text("SELECT status FROM billing_event_inbox WHERE id=:id"), {"id": retry_id}
                    )
                    == "admitted"
                )
                assert (
                    await connection.scalar(
                        text("""
                        SELECT app_private.admit_stripe_sync_event(:event,'subscription.snapshot',
                          'sub_other',:now,CAST(:payload AS jsonb))
                    """),
                        {"event": f"evt_{retry_id.hex}", "now": now, "payload": json.dumps(retry_payload)},
                    )
                    is False
                )
            finally:
                await transaction.rollback()
    finally:
        await database.close()
