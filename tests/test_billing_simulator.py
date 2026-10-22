import hashlib
import hmac
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.application.errors import BillingOperationError
from backend.app.application.ports.billing import (
    BillingCheckoutCommand,
    BillingPortalCommand,
    BillingReturnTarget,
)
from backend.app.config import Settings
from backend.app.domain.billing import BillingErrorCode, BillingEventType, SubscriptionState
from backend.app.domain.catalog import CurrencyCode
from backend.app.infrastructure.billing import (
    DisabledBillingProviderGateway,
    SimulatedBillingProviderGateway,
    SimulatedWebhookScenario,
    build_billing_provider_gateway,
)

_NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)
_SECRET = b"simulated-billing-webhook-secret-for-tests"


def _gateway() -> SimulatedBillingProviderGateway:
    return SimulatedBillingProviderGateway(webhook_secret=_SECRET, clock=lambda: _NOW)


def _checkout(price_reference: str = "price_simulated_monthly") -> BillingCheckoutCommand:
    return BillingCheckoutCommand(
        organization_id=uuid4(),
        plan_version_id=uuid4(),
        currency=CurrencyCode.CAD,
        provider_price_reference=price_reference,
        return_target=BillingReturnTarget.SUBSCRIPTION,
    )


@pytest.mark.asyncio
async def test_disabled_billing_gateway_fails_closed_without_provider_access() -> None:
    gateway = DisabledBillingProviderGateway()

    with pytest.raises(BillingOperationError) as error:
        await gateway.create_checkout(command=_checkout(), idempotency_key="checkout-1")

    assert error.value.code is BillingErrorCode.PROVIDER_DISABLED


@pytest.mark.asyncio
async def test_simulator_replays_an_identical_checkout_and_refuses_a_key_collision() -> None:
    gateway = _gateway()
    command = _checkout()

    first = await gateway.create_checkout(command=command, idempotency_key="checkout-1")
    replay = await gateway.create_checkout(command=command, idempotency_key="checkout-1")

    assert replay == first
    assert first.checkout_url.startswith("http://billing-simulator.local/")
    assert "price_simulated_monthly" not in first.checkout_url

    with pytest.raises(BillingOperationError) as error:
        await gateway.create_checkout(command=_checkout("other-price"), idempotency_key="checkout-1")

    assert error.value.code is BillingErrorCode.COMMAND_CONFLICT


@pytest.mark.asyncio
async def test_simulator_uses_separate_idempotency_namespaces_for_checkout_and_portal() -> None:
    gateway = _gateway()
    checkout = await gateway.create_checkout(command=_checkout(), idempotency_key="same-key")
    portal = await gateway.create_portal_session(
        command=BillingPortalCommand(uuid4(), "sim_customer_opaque", BillingReturnTarget.SUBSCRIPTION),
        idempotency_key="same-key",
    )

    assert checkout.provider_checkout_reference != portal.provider_portal_reference
    assert portal.portal_url.startswith("http://billing-simulator.local/")


@pytest.mark.asyncio
@pytest.mark.parametrize("currency", list(CurrencyCode))
async def test_simulator_emits_a_deterministic_signed_webhook_without_network(currency: CurrencyCode) -> None:
    gateway = _gateway()
    checkout = await gateway.create_checkout(
        command=replace(_checkout(), currency=currency), idempotency_key="checkout-1"
    )

    delivery = gateway.emit_webhook(
        checkout_reference=checkout.provider_checkout_reference,
        scenario=SimulatedWebhookScenario.INVOICE_PAID,
    )

    timestamp, signature = delivery.signature_header.split(",")
    expected = hmac.new(
        _SECRET,
        timestamp.removeprefix("t=").encode("ascii") + b"." + delivery.raw_body,
        hashlib.sha256,
    ).hexdigest()
    snapshot = await gateway.get_subscription(provider_subscription_reference=delivery.event.provider_object_reference)

    assert signature == f"v1={expected}"
    assert delivery.event.event_type is BillingEventType.INVOICE_PAID
    assert snapshot.state is SubscriptionState.ACTIVE
    assert snapshot.currency is currency
    assert delivery.event.normalized_subscription is not None
    assert delivery.event.normalized_subscription.currency is currency
    assert b"card" not in delivery.raw_body.lower()


@pytest.mark.asyncio
async def test_simulator_exposes_duplicate_collision_and_stale_deliveries_for_future_admission_tests() -> None:
    gateway = _gateway()
    checkout = await gateway.create_checkout(command=_checkout(), idempotency_key="checkout-1")
    first = gateway.emit_webhook(
        checkout_reference=checkout.provider_checkout_reference,
        scenario=SimulatedWebhookScenario.INVOICE_PAID,
    )
    duplicate = gateway.emit_webhook(
        checkout_reference=checkout.provider_checkout_reference,
        scenario=SimulatedWebhookScenario.DUPLICATE_EVENT,
    )
    collision = gateway.emit_webhook(
        checkout_reference=checkout.provider_checkout_reference,
        scenario=SimulatedWebhookScenario.EVENT_ID_COLLISION,
    )
    stale = gateway.emit_webhook(
        checkout_reference=checkout.provider_checkout_reference,
        scenario=SimulatedWebhookScenario.STALE_EVENT,
    )

    assert duplicate == first
    assert collision.event.provider_event_id == first.event.provider_event_id
    assert collision.raw_body != first.raw_body
    assert stale.event.provider_created_at == _NOW - timedelta(minutes=10)


@pytest.mark.asyncio
async def test_simulator_fails_closed_for_unavailable_provider_scenarios() -> None:
    gateway = _gateway()
    gateway.configure_next_scenario(SimulatedWebhookScenario.PROVIDER_UNAVAILABLE)

    with pytest.raises(BillingOperationError) as error:
        await gateway.create_checkout(command=_checkout(), idempotency_key="checkout-1")

    assert error.value.code is BillingErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
async def test_simulator_marks_a_timeout_after_effect_for_reconciliation_without_second_checkout() -> None:
    gateway = _gateway()
    command = _checkout()
    gateway.configure_next_scenario(SimulatedWebhookScenario.PROVIDER_TIMEOUT_AFTER_EFFECT)

    with pytest.raises(BillingOperationError) as error:
        await gateway.create_checkout(command=command, idempotency_key="checkout-1")
    replay = await gateway.create_checkout(command=command, idempotency_key="checkout-1")

    assert error.value.code is BillingErrorCode.RECONCILIATION_REQUIRED
    assert replay.provider_checkout_reference.startswith("sim_")


def test_billing_adapter_selection_has_no_silent_sandbox_fallback() -> None:
    assert isinstance(build_billing_provider_gateway(Settings()), DisabledBillingProviderGateway)
    assert isinstance(
        build_billing_provider_gateway(
            Settings(
                app_env="test",
                billing_provider_mode="simulated",
                billing_simulator_webhook_secret="s" * 32,
            ),
            clock=lambda: _NOW,
        ),
        SimulatedBillingProviderGateway,
    )
    with pytest.raises(RuntimeError, match="sandbox"):
        build_billing_provider_gateway(Settings(billing_provider_mode="stripe_sandbox"))
