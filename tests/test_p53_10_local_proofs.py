"""Preuves synthétiques additionnelles de la recette P53-10."""

from __future__ import annotations

import smtplib
import socket
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.application.ports.billing import (
    BillingCheckoutCommand,
    BillingReturnTarget,
    BillingWebhookAdmissionCode,
    NormalizedBillingEvent,
)
from backend.app.domain.catalog import CurrencyCode
from backend.app.infrastructure.billing.simulated import SimulatedBillingProviderGateway, SimulatedWebhookScenario
from backend.app.infrastructure.billing.webhooks import BillingWebhookAdmissionService, SimulatedBillingWebhookVerifier

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)
SECRET = b"p53-10-synthetic-webhook-secret-for-tests"


class _CountingInbox:
    def __init__(self) -> None:
        self.events: dict[str, str] = {}
        self.admitted = 0

    async def admit(self, *, event: NormalizedBillingEvent, payload_digest: str) -> BillingWebhookAdmissionCode:
        event_id = event.provider_event_id
        previous = self.events.get(event_id)
        if previous is None:
            self.events[event_id] = payload_digest
            self.admitted += 1
            return BillingWebhookAdmissionCode.ADMITTED
        if previous == payload_digest:
            return BillingWebhookAdmissionCode.DUPLICATE
        return BillingWebhookAdmissionCode.COLLISION


def _checkout() -> BillingCheckoutCommand:
    return BillingCheckoutCommand(
        organization_id=uuid4(),
        plan_version_id=uuid4(),
        currency=CurrencyCode.CAD,
        provider_price_reference="price_synthetic",
        return_target=BillingReturnTarget.SUBSCRIPTION,
    )


@pytest.mark.asyncio
async def test_p53_10_hundred_webhook_deliveries_admit_once() -> None:
    gateway = SimulatedBillingProviderGateway(webhook_secret=SECRET, clock=lambda: NOW)
    checkout = await gateway.create_checkout(command=_checkout(), idempotency_key="same-checkout")
    delivery = gateway.emit_webhook(
        checkout_reference=checkout.provider_checkout_reference,
        scenario=SimulatedWebhookScenario.INVOICE_PAID,
    )
    inbox = _CountingInbox()
    admission = BillingWebhookAdmissionService(
        SimulatedBillingWebhookVerifier(current_secret=SECRET, tolerance_seconds=300), inbox, clock=lambda: NOW
    )

    results = [
        await admission.admit(raw_body=delivery.raw_body, signature_header=delivery.signature_header)
        for _ in range(100)
    ]

    assert results == [BillingWebhookAdmissionCode.ADMITTED] + [BillingWebhookAdmissionCode.DUPLICATE] * 99
    assert inbox.admitted == 1
    assert len(inbox.events) == 1


@pytest.mark.asyncio
async def test_p53_10_simulator_has_no_network_or_smtp_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[str] = []

    def blocked(*_args: object, **_kwargs: object) -> None:
        attempts.append("external-call")
        raise AssertionError("Le simulateur ne doit effectuer aucun appel DNS, réseau ou SMTP.")

    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(smtplib, "SMTP", blocked)
    monkeypatch.setattr(smtplib, "SMTP_SSL", blocked)

    gateway = SimulatedBillingProviderGateway(webhook_secret=SECRET, clock=lambda: NOW)
    checkout = await gateway.create_checkout(command=_checkout(), idempotency_key="no-network")
    delivery = gateway.emit_webhook(
        checkout_reference=checkout.provider_checkout_reference,
        scenario=SimulatedWebhookScenario.INVOICE_PAID,
    )
    verified = SimulatedBillingWebhookVerifier(current_secret=SECRET, tolerance_seconds=300).verify(
        raw_body=delivery.raw_body,
        signature_header=delivery.signature_header,
        received_at=NOW,
    )
    snapshot = await gateway.get_subscription(provider_subscription_reference=verified.provider_object_reference)

    assert verified.provider_event_id
    assert snapshot.currency is CurrencyCode.CAD
    assert attempts == []
