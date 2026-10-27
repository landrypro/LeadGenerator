"""Recette P53-10 : livraisons signées, reprise et effet métier durable unique."""

from __future__ import annotations

import asyncio
import os
import smtplib
import socket
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from backend.app.application.ports.billing import BillingCheckoutCommand, BillingReturnTarget
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.catalog import CurrencyCode
from backend.app.infrastructure.billing.simulated import SimulatedBillingProviderGateway, SimulatedWebhookScenario
from backend.app.infrastructure.billing.webhooks import BillingWebhookAdmissionService, SimulatedBillingWebhookVerifier
from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.billing_projection import BillingProjectionWorker
from backend.app.infrastructure.postgres.billing_webhook_inbox import SqlAlchemyBillingEventInbox

pytestmark = pytest.mark.integration
SECRET = b"p53-10-local-only-signed-webhook-secret"


def _database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=10,
        pool_size=2,
        max_overflow=0,
        pool_timeout_seconds=10,
        statement_timeout_ms=10_000,
    )


def _webhook_app(database: PostgresDatabase, now: datetime) -> object:
    admission = BillingWebhookAdmissionService(
        SimulatedBillingWebhookVerifier(current_secret=SECRET, tolerance_seconds=300),
        SqlAlchemyBillingEventInbox(database.session_factory),
        clock=lambda: now,
    )
    return create_app(
        container=AppContainer(
            settings=Settings(),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            billing_webhook_admission=admission,
        )
    )


async def test_hundred_signed_webhooks_across_restart_have_one_durable_effect_and_no_external_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    worker_url = os.environ.get("TEST_WORKER_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not app_url or not worker_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("Les trois rôles PostgreSQL de test sont requis pour P53-10.")
        pytest.skip("Les trois rôles PostgreSQL de test sont absents.")

    app_db, worker_db, owner_db = _database(app_url), _database(worker_url), _database(owner_url)
    app_after_restart: PostgresDatabase | None = None
    actor, approver, organization, plan, version, customer, subscription = (uuid4() for _ in range(7))
    now = datetime.now(UTC).replace(microsecond=0)
    gateway = SimulatedBillingProviderGateway(webhook_secret=SECRET, clock=lambda: now)
    checkout = await gateway.create_checkout(
        command=BillingCheckoutCommand(
            organization_id=organization,
            plan_version_id=version,
            currency=CurrencyCode.CAD,
            provider_price_reference="price_p53_10_synthetic",
            return_target=BillingReturnTarget.SUBSCRIPTION,
        ),
        idempotency_key="p53-10-hundred-webhooks",
    )
    delivery = gateway.emit_webhook(
        checkout_reference=checkout.provider_checkout_reference,
        scenario=SimulatedWebhookScenario.INVOICE_PAID,
    )
    event_id = delivery.event.provider_event_id
    customer_reference = checkout.provider_customer_reference
    subscription_reference = checkout.provider_subscription_reference
    params = {
        "actor": actor,
        "approver": approver,
        "organization": organization,
        "plan": plan,
        "version": version,
        "customer": customer,
        "subscription": subscription,
        "actor_email": f"p53-proof-{actor}@example.test",
        "approver_email": f"p53-proof-{approver}@example.test",
        "customer_reference": customer_reference,
        "subscription_reference": subscription_reference,
        "event_id": event_id,
        "now": now,
        "previous": now - timedelta(minutes=1),
        "end": now + timedelta(days=30),
    }
    attempts: list[str] = []
    database_endpoint = make_url(app_url)
    allowed_hosts = {database_endpoint.host, "localhost", "127.0.0.1", "::1"}
    allowed_port = database_endpoint.port
    original_getaddrinfo = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = asyncio.BaseEventLoop.create_connection
    event_loop = asyncio.get_running_loop()
    original_sock_connect = event_loop.sock_connect

    def allowed(address: object) -> bool:
        return (
            isinstance(address, tuple)
            and len(address) >= 2
            and address[0] in allowed_hosts
            and address[1] == allowed_port
        )

    def guarded_getaddrinfo(host: object, port: object, *args: object, **kwargs: object) -> object:
        if host not in allowed_hosts or port != allowed_port:
            attempts.append("dns")
            raise AssertionError("Résolution externe interdite pendant la recette P53-10.")
        return original_getaddrinfo(host, port, *args, **kwargs)

    def guarded_connect(self: socket.socket, address: object) -> object:
        if not allowed(address):
            attempts.append("tcp")
            raise AssertionError("Connexion externe interdite pendant la recette P53-10.")
        return original_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: object) -> object:
        if not allowed(address):
            attempts.append("tcp")
            raise AssertionError("Connexion externe interdite pendant la recette P53-10.")
        return original_connect_ex(self, address)

    async def guarded_async_connect(
        loop: asyncio.BaseEventLoop,
        protocol_factory: object,
        host: str | None = None,
        port: int | None = None,
        *args: object,
        **kwargs: object,
    ) -> object:
        if host is not None and not allowed((host, port)):
            attempts.append("async-tcp")
            raise AssertionError("Connexion asynchrone externe interdite pendant la recette P53-10.")
        return await original_create_connection(loop, protocol_factory, host, port, *args, **kwargs)

    async def guarded_sock_connect(loop: asyncio.AbstractEventLoop, sock: socket.socket, address: object) -> None:
        if not allowed(address):
            attempts.append("async-sock")
            raise AssertionError("Connexion socket asynchrone externe interdite pendant la recette P53-10.")
        await original_sock_connect(sock, address)

    def blocked_smtp(*_args: object, **_kwargs: object) -> None:
        attempts.append("smtp")
        raise AssertionError("SMTP interdit pendant la recette P53-10.")

    try:
        async with owner_db.engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO users (id,email,email_normalized,display_name,password_hash,status,created_at,updated_at) "
                    "VALUES (:actor,:actor_email,:actor_email,'P53 proof','hash','active',:now,:now),"
                    "(:approver,:approver_email,:approver_email,'P53 approval','hash','active',:now,:now)"
                ),
                params,
            )
            await connection.execute(
                text(
                    "INSERT INTO organizations (id,name,timezone,status,created_by,activated_at,created_at,updated_at) "
                    "VALUES (:organization,'P53 proof','America/Toronto','active',:actor,:now,:now,:now)"
                ),
                params,
            )
            await connection.execute(
                text("INSERT INTO plan_catalog (id,code,state) VALUES (:plan,'custom','draft')"), params
            )
            await connection.execute(
                text(
                    "INSERT INTO plan_versions (id,plan_id,version_number,state,currency,billing_cycle,"
                    "amount_excluding_tax_minor,effective_from,created_by_user_id,approved_by_user_id,published_at) "
                    "VALUES (:version,:plan,1,'published','CAD','monthly',0,:now,:actor,:approver,:now)"
                ),
                params,
            )
            await connection.execute(
                text(
                    "INSERT INTO billing_customers (id,organization_id,provider,provider_customer_reference) "
                    "VALUES (:customer,:organization,'simulated',:customer_reference)"
                ),
                params,
            )
            await connection.execute(
                text(
                    "INSERT INTO subscriptions (id,organization_id,billing_customer_id,provider,"
                    "provider_subscription_reference,plan_version_id,currency,state,current_period_start,"
                    "current_period_end,provider_updated_at) VALUES (:subscription,:organization,:customer,"
                    "'simulated',:subscription_reference,:version,'CAD','pending_checkout',:previous,:end,:previous)"
                ),
                params,
            )

        with monkeypatch.context() as guard:
            guard.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
            guard.setattr(socket.socket, "connect", guarded_connect)
            guard.setattr(socket.socket, "connect_ex", guarded_connect_ex)
            guard.setattr(asyncio.BaseEventLoop, "create_connection", guarded_async_connect)
            guard.setattr(type(event_loop), "sock_connect", guarded_sock_connect)
            guard.setattr(smtplib, "SMTP", blocked_smtp)
            guard.setattr(smtplib, "SMTP_SSL", blocked_smtp)
            probe = socket.socket()
            probe.setblocking(False)
            try:
                with pytest.raises(AssertionError, match="socket asynchrone externe"):
                    await event_loop.sock_connect(probe, ("203.0.113.1", 443))
            finally:
                probe.close()
            assert attempts == ["async-sock"]
            attempts.clear()
            for batch in range(2):
                database = app_db if batch == 0 else _database(app_url)
                if batch == 1:
                    app_after_restart = database
                async with AsyncClient(
                    transport=ASGITransport(app=_webhook_app(database, now)), base_url="http://test"
                ) as client:
                    for index in range(50):
                        response = await client.post(
                            "/api/billing/webhooks/simulated",
                            content=delivery.raw_body,
                            headers={
                                "content-type": "application/json",
                                "x-billing-signature": delivery.signature_header,
                            },
                        )
                        assert response.status_code == (202 if batch == 0 and index == 0 else 200)
                if batch == 0:
                    await app_db.close()

            first_worker = BillingProjectionWorker(worker_db.session_factory)
            assert await first_worker.run_once() is True
            assert await BillingProjectionWorker(worker_db.session_factory).run_once() is False
            assert attempts == []

        async with owner_db.engine.connect() as connection:
            inbox = await connection.execute(
                text(
                    "SELECT id,status FROM billing_event_inbox WHERE provider='simulated' AND provider_event_id=:event_id"
                ),
                params,
            )
            rows = inbox.all()
            assert len(rows) == 1 and rows[0].status == "processed"
            inbox_id = rows[0].id
            events = await connection.scalar(
                text("SELECT count(*) FROM billing_events WHERE inbox_id=:id"), {"id": inbox_id}
            )
            transitions = await connection.scalar(
                text("SELECT count(*) FROM subscription_transitions WHERE subscription_id=:subscription"), params
            )
            audits = await connection.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE entity_id=:subscription "
                    "AND action='billing.subscription_transition_applied'"
                ),
                params,
            )
            state = await connection.scalar(text("SELECT state FROM subscriptions WHERE id=:subscription"), params)
        assert events == transitions == audits == 1
        assert state == "active"
    finally:
        async with owner_db.engine.begin() as connection:
            await connection.execute(
                text(
                    "DELETE FROM simulated_billing_provider_subscriptions WHERE provider_subscription_reference=:subscription_reference"
                ),
                params,
            )
            await connection.execute(text("DELETE FROM audit_events WHERE entity_id=:subscription"), params)
            await connection.execute(
                text("DELETE FROM subscription_transitions WHERE subscription_id=:subscription"), params
            )
            await connection.execute(
                text(
                    "DELETE FROM billing_events WHERE inbox_id IN (SELECT id FROM billing_event_inbox WHERE provider_event_id=:event_id)"
                ),
                params,
            )
            await connection.execute(text("DELETE FROM billing_event_inbox WHERE provider_event_id=:event_id"), params)
            await connection.execute(text("DELETE FROM subscriptions WHERE id=:subscription"), params)
            await connection.execute(text("DELETE FROM billing_customers WHERE id=:customer"), params)
            await connection.execute(text("UPDATE plan_versions SET state='superseded' WHERE id=:version"), params)
            await connection.execute(text("DELETE FROM plan_versions WHERE id=:version"), params)
            await connection.execute(text("DELETE FROM plan_catalog WHERE id=:plan"), params)
            await connection.execute(text("DELETE FROM organizations WHERE id=:organization"), params)
            await connection.execute(text("DELETE FROM users WHERE id IN (:actor,:approver)"), params)
        await app_db.close()
        if app_after_restart is not None:
            await app_after_restart.close()
        await worker_db.close()
        await owner_db.close()
