import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import BillingOperationError
from backend.app.application.ports.billing import (
    BillingCheckoutCommand,
    BillingReturnTarget,
    BillingWebhookAdmissionCode,
)
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.billing import BillingErrorCode
from backend.app.domain.catalog import CurrencyCode
from backend.app.infrastructure.billing.simulated import (
    SimulatedBillingProviderGateway,
    SimulatedWebhookDelivery,
    SimulatedWebhookScenario,
)
from backend.app.infrastructure.billing.webhooks import BillingWebhookAdmissionService, SimulatedBillingWebhookVerifier

_NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)
_SECRET = b"simulated-billing-webhook-secret-for-tests"


class _Inbox:
    def __init__(self) -> None:
        self.by_event: dict[str, str] = {}

    async def admit(self, *, event, payload_digest: str) -> BillingWebhookAdmissionCode:  # type: ignore[no-untyped-def]
        existing = self.by_event.get(event.provider_event_id)
        if existing is None:
            self.by_event[event.provider_event_id] = payload_digest
            return BillingWebhookAdmissionCode.ADMITTED
        return (
            BillingWebhookAdmissionCode.DUPLICATE
            if existing == payload_digest
            else BillingWebhookAdmissionCode.COLLISION
        )


class _Admission:
    def __init__(self, code: BillingWebhookAdmissionCode) -> None:
        self.code = code
        self.calls: list[tuple[bytes, str]] = []

    async def admit(self, *, raw_body: bytes, signature_header: str) -> BillingWebhookAdmissionCode:
        self.calls.append((raw_body, signature_header))
        return self.code


async def _delivery() -> tuple[SimulatedBillingProviderGateway, SimulatedWebhookDelivery]:
    gateway = SimulatedBillingProviderGateway(webhook_secret=_SECRET, clock=lambda: _NOW)
    checkout = await gateway.create_checkout(
        command=BillingCheckoutCommand(
            organization_id=uuid4(),
            plan_version_id=uuid4(),
            currency=CurrencyCode.CAD,
            provider_price_reference="price_simulated_monthly",
            return_target=BillingReturnTarget.SUBSCRIPTION,
        ),
        idempotency_key="checkout-1",
    )
    return gateway, gateway.emit_webhook(
        checkout_reference=checkout.provider_checkout_reference, scenario=SimulatedWebhookScenario.INVOICE_PAID
    )


@pytest.mark.asyncio
async def test_webhook_admission_verifies_raw_hmac_then_deduplicates_and_detects_collision() -> None:
    _, delivery = await _delivery()
    inbox = _Inbox()
    service = BillingWebhookAdmissionService(
        SimulatedBillingWebhookVerifier(current_secret=_SECRET, tolerance_seconds=300), inbox, clock=lambda: _NOW
    )

    assert (
        await service.admit(raw_body=delivery.raw_body, signature_header=delivery.signature_header)
        is BillingWebhookAdmissionCode.ADMITTED
    )
    assert (
        await service.admit(raw_body=delivery.raw_body, signature_header=delivery.signature_header)
        is BillingWebhookAdmissionCode.DUPLICATE
    )
    payload = json.loads(delivery.raw_body)
    payload["data"]["object"]["reference"] = "sim_changed"
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    timestamp = int(_NOW.timestamp())
    signature = hmac.new(_SECRET, f"{timestamp}.".encode("ascii") + body, hashlib.sha256).hexdigest()
    assert (
        await service.admit(raw_body=body, signature_header=f"t={timestamp},v1={signature}")
        is BillingWebhookAdmissionCode.COLLISION
    )


@pytest.mark.asyncio
async def test_webhook_admission_rejects_bad_or_expired_signature_before_deserializing() -> None:
    _, delivery = await _delivery()
    verifier = SimulatedBillingWebhookVerifier(current_secret=_SECRET, tolerance_seconds=300)

    with pytest.raises(BillingOperationError) as invalid:
        verifier.verify(raw_body=b"not-json", signature_header=delivery.signature_header, received_at=_NOW)
    assert invalid.value.code is BillingErrorCode.WEBHOOK_INVALID

    with pytest.raises(BillingOperationError) as expired:
        verifier.verify(raw_body=delivery.raw_body, signature_header="t=0,v1=" + "0" * 64, received_at=_NOW)
    assert expired.value.code is BillingErrorCode.WEBHOOK_INVALID


@pytest.mark.asyncio
async def test_webhook_admission_accepts_previous_key_but_rejects_unknown_schema() -> None:
    old_secret = b"old-simulated-billing-webhook-secret-tests"
    gateway = SimulatedBillingProviderGateway(webhook_secret=old_secret, clock=lambda: _NOW)
    checkout = await gateway.create_checkout(
        command=BillingCheckoutCommand(
            uuid4(), uuid4(), CurrencyCode.CAD, "price_simulated", BillingReturnTarget.SUBSCRIPTION
        ),
        idempotency_key="checkout-old",
    )
    delivery = gateway.emit_webhook(
        checkout_reference=checkout.provider_checkout_reference, scenario=SimulatedWebhookScenario.INVOICE_PAID
    )
    verifier = SimulatedBillingWebhookVerifier(
        current_secret=_SECRET, previous_secret=old_secret, tolerance_seconds=300
    )
    assert verifier.verify(
        raw_body=delivery.raw_body, signature_header=delivery.signature_header, received_at=_NOW
    ).provider_event_id

    payload = json.loads(delivery.raw_body)
    payload["api_version"] = "unknown-version"
    raw_body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(old_secret, f"{int(_NOW.timestamp())}.".encode("ascii") + raw_body, hashlib.sha256).hexdigest()
    with pytest.raises(BillingOperationError) as unsupported:
        verifier.verify(
            raw_body=raw_body, signature_header=f"t={int(_NOW.timestamp())},v1={signature}", received_at=_NOW
        )
    assert unsupported.value.code is BillingErrorCode.WEBHOOK_UNSUPPORTED

    payload["api_version"] = "simulated-2026-10-09"
    payload["type"] = "unknown.event"
    raw_body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(old_secret, f"{int(_NOW.timestamp())}.".encode("ascii") + raw_body, hashlib.sha256).hexdigest()
    with pytest.raises(BillingOperationError) as unsupported_type:
        verifier.verify(
            raw_body=raw_body, signature_header=f"t={int(_NOW.timestamp())},v1={signature}", received_at=_NOW
        )
    assert unsupported_type.value.code is BillingErrorCode.WEBHOOK_UNSUPPORTED


@pytest.mark.asyncio
async def test_webhook_api_requires_raw_json_and_returns_minimized_stable_responses() -> None:
    admission = _Admission(BillingWebhookAdmissionCode.ADMITTED)
    app = create_app(
        container=AppContainer(
            settings=Settings(),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            billing_webhook_admission=admission,  # type: ignore[arg-type]
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/billing/webhooks/simulated",
            content=b"{}",
            headers={"content-type": "application/json", "x-billing-signature": "opaque"},
        )
        assert response.status_code == 202
        assert response.json() == {"status": "accepted"}
        assert response.headers["cache-control"] == "no-store, max-age=0"

        invalid = await client.post(
            "/api/billing/webhooks/simulated", content=b"{}", headers={"content-type": "text/plain"}
        )
        assert invalid.status_code == 400
        assert invalid.json()["error"]["code"] == BillingErrorCode.WEBHOOK_INVALID.value

        too_large = await client.post(
            "/api/billing/webhooks/simulated",
            content=b"x" * (64 * 1024 + 1),
            headers={"content-type": "application/json"},
        )
        assert too_large.status_code == 400

    assert admission.calls == [(b"{}", "opaque")]


@pytest.mark.asyncio
async def test_webhook_api_exposes_collision_as_409_without_provider_details() -> None:
    admission = _Admission(BillingWebhookAdmissionCode.COLLISION)
    app = create_app(
        container=AppContainer(
            settings=Settings(),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            billing_webhook_admission=admission,  # type: ignore[arg-type]
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/billing/webhooks/simulated",
            content=b"{}",
            headers={"content-type": "application/json", "x-billing-signature": "opaque"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == BillingErrorCode.EVENT_COLLISION.value


@pytest.mark.asyncio
async def test_stripe_webhook_api_uses_its_distinct_signature_header_and_admission() -> None:
    admission = _Admission(BillingWebhookAdmissionCode.ADMITTED)
    app = create_app(
        container=AppContainer(
            settings=Settings(),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            billing_stripe_webhook_admission=admission,  # type: ignore[arg-type]
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/billing/webhooks/stripe",
            content=b"{}",
            headers={"content-type": "application/json", "stripe-signature": "stripe-opaque"},
        )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert admission.calls == [(b"{}", "stripe-opaque")]
