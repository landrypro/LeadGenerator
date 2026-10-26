"""Contrat de signature et de normalisation Stripe P53-09, sans réseau."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from backend.app.application.errors import BillingOperationError
from backend.app.application.ports.billing import BillingCheckoutCommand, BillingReturnTarget
from backend.app.config import Settings
from backend.app.domain.billing import BillingErrorCode, BillingEventType, SubscriptionState
from backend.app.domain.catalog import CurrencyCode
from backend.app.infrastructure.billing.stripe_client import StripeSandboxClient
from backend.app.infrastructure.billing.stripe_contract import STRIPE_API_VERSION, StripeSandboxWebhookVerifier
from backend.app.infrastructure.billing.stripe_sandbox import StripeSandboxProviderGateway

_SECRET = "whsec_synthetic_for_contract_testing"
_CREATED = 1_793_000_000
_NOW = datetime.fromtimestamp(_CREATED, UTC)


def _payload(
    *,
    currency: str = "xaf",
    api_version: str = STRIPE_API_VERSION,
    livemode: bool = False,
    command_id: str | None = None,
) -> bytes:
    subscription = {
        "id": "sub_test_contract",
        "object": "subscription",
        "livemode": livemode,
        "customer": "cus_test_contract",
        "currency": currency,
        "status": "incomplete",
        "cancel_at_period_end": False,
        "metadata": {} if command_id is None else {"billing_command_id": command_id},
        "items": {
            "data": [
                {
                    "current_period_start": _CREATED,
                    "current_period_end": _CREATED + 2_592_000,
                    "price": {"id": "price_test_contract", "currency": currency, "recurring": {"interval": "month"}},
                }
            ]
        },
    }
    return json.dumps(
        {
            "id": "evt_test_contract",
            "object": "event",
            "api_version": api_version,
            "livemode": livemode,
            "created": _CREATED,
            "type": "customer.subscription.created",
            "data": {"object": subscription},
        },
        separators=(",", ":"),
    ).encode()


def _signed(raw: bytes, *, timestamp: int = _CREATED, secret: str = _SECRET) -> str:
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + raw, hashlib.sha256).hexdigest()
    return f"t={timestamp},v0=ignored,v1=invalid,v1={digest}"


def test_signed_subscription_is_normalized_without_currency_conversion() -> None:
    command_id = uuid4()
    raw = _payload(command_id=str(command_id))
    event = StripeSandboxWebhookVerifier(secret=_SECRET, tolerance_seconds=300).verify(
        raw_body=raw, signature_header=_signed(raw), received_at=_NOW
    )
    assert event.event_type is BillingEventType.SUBSCRIPTION_SNAPSHOT
    assert event.normalized_subscription is not None
    assert event.normalized_subscription.state is SubscriptionState.PENDING_CHECKOUT
    assert event.normalized_subscription.currency is CurrencyCode.XAF
    assert event.normalized_subscription.provider_price_reference == "price_test_contract"
    assert event.checkout_command_id == command_id


def test_subscription_without_checkout_metadata_stays_unlinked() -> None:
    raw = _payload()
    event = StripeSandboxWebhookVerifier(secret=_SECRET, tolerance_seconds=300).verify(
        raw_body=raw, signature_header=_signed(raw), received_at=_NOW
    )
    assert event.checkout_command_id is None


@pytest.mark.parametrize(
    ("raw", "header", "received_at", "code"),
    [
        (_payload(), "t=1793000000,v1=invalid", _NOW, BillingErrorCode.WEBHOOK_INVALID),
        (_payload(), _signed(_payload(), timestamp=_CREATED - 301), _NOW, BillingErrorCode.WEBHOOK_INVALID),
        (_payload(api_version="2025-06-30.basil"), "", _NOW, BillingErrorCode.WEBHOOK_INVALID),
    ],
)
def test_bad_signature_and_expired_delivery_are_rejected(
    raw: bytes, header: str, received_at: datetime, code: BillingErrorCode
) -> None:
    verifier = StripeSandboxWebhookVerifier(secret=_SECRET, tolerance_seconds=300)
    with pytest.raises(BillingOperationError) as error:
        verifier.verify(raw_body=raw, signature_header=header, received_at=received_at)
    assert error.value.code is code


def test_api_version_and_live_event_are_rejected_after_signature() -> None:
    verifier = StripeSandboxWebhookVerifier(secret=_SECRET, tolerance_seconds=300)
    for raw, expected in (
        (_payload(api_version="2025-06-30.basil"), BillingErrorCode.WEBHOOK_UNSUPPORTED),
        (_payload(livemode=True), BillingErrorCode.WEBHOOK_INVALID),
    ):
        with pytest.raises(BillingOperationError) as error:
            verifier.verify(raw_body=raw, signature_header=_signed(raw), received_at=_NOW)
        assert error.value.code is expected


def test_checkout_and_invoice_cannot_be_acknowledged_without_durable_mapping() -> None:
    verifier = StripeSandboxWebhookVerifier(secret=_SECRET, tolerance_seconds=300)
    for stripe_type in ("checkout.session.completed", "invoice.paid", "invoice.payment_failed"):
        payload = json.loads(_payload())
        payload["type"] = stripe_type
        raw = json.dumps(payload).encode()
        with pytest.raises(BillingOperationError) as error:
            verifier.verify(raw_body=raw, signature_header=_signed(raw), received_at=_NOW)
        assert error.value.code is BillingErrorCode.WEBHOOK_UNSUPPORTED


def test_rotated_webhook_secret_is_accepted_without_accepting_live_api_keys() -> None:
    raw = _payload(currency="cad")
    verifier = StripeSandboxWebhookVerifier(
        secret="whsec_new_synthetic_for_contract", previous_secret=_SECRET, tolerance_seconds=300
    )
    event = verifier.verify(raw_body=raw, signature_header=_signed(raw), received_at=_NOW)
    assert event.normalized_subscription is not None
    assert event.normalized_subscription.currency is CurrencyCode.CAD
    with pytest.raises(ValueError):
        Settings(app_env="test", billing_provider_mode="stripe_sandbox", billing_stripe_test_secret_key="sk_live_bad")
    with pytest.raises(ValueError):
        Settings(
            app_env="production",
            billing_provider_mode="stripe_sandbox",
            billing_stripe_test_secret_key="sk_test_synthetic",
            billing_stripe_webhook_secret=_SECRET,
        )


@pytest.mark.parametrize("placeholder", ["sk_test_…", "sk_test_..."])
def test_stripe_sandbox_rejects_example_api_key(placeholder: str) -> None:
    with pytest.raises(ValueError, match="vraie clé de test"):
        Settings(
            app_env="development",
            billing_provider_mode="stripe_sandbox",
            billing_stripe_test_secret_key=placeholder,
            billing_stripe_webhook_secret="whsec_synthetic",
        )


@pytest.mark.parametrize("placeholder", ["whsec_…", "whsec_..."])
def test_stripe_sandbox_rejects_example_webhook_secret(placeholder: str) -> None:
    with pytest.raises(ValueError, match="secret du listener"):
        Settings(
            app_env="development",
            billing_provider_mode="stripe_sandbox",
            billing_stripe_test_secret_key="sk_test_synthetic",
            billing_stripe_webhook_secret=placeholder,
        )


@pytest.mark.asyncio
async def test_checkout_uses_pinned_version_idempotency_and_recurring_price() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/prices/price_test_contract":
            return httpx.Response(
                200,
                json={
                    "object": "price",
                    "id": "price_test_contract",
                    "livemode": False,
                    "active": True,
                    "currency": "xaf",
                    "unit_amount": 5000,
                    "type": "recurring",
                    "recurring": {"interval": "month", "interval_count": 1},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "cs_test_contract",
                "url": "https://checkout.stripe.com/c/pay/cs_test_contract",
                "expires_at": _CREATED + 3600,
                "livemode": False,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = StripeSandboxClient(test_secret_key="sk_test_synthetic", client=http_client)
        draft = await client.create_checkout(
            customer_reference="cus_test_contract",
            price_reference="price_test_contract",
            checkout_command_reference=str(uuid4()),
            currency=CurrencyCode.XAF,
            amount_minor=5000,
            billing_cycle="monthly",
            return_origin="http://localhost:5173",
            idempotency_key="checkout:synthetic",
        )
    assert draft.reference == "cs_test_contract"
    assert len(seen) == 2
    assert all(request.headers["Stripe-Version"] == STRIPE_API_VERSION for request in seen)
    assert seen[1].headers["Idempotency-Key"] == "checkout:synthetic"
    assert b"mode=subscription" in seen[1].content
    assert b"price_test_contract" in seen[1].content
    assert b"subscription_data%5Bmetadata%5D%5Bbilling_command_id%5D" in seen[1].content
    assert b"%2Fapp%2Fbilling%3Fcheckout%3Dsuccess" in seen[1].content
    assert b"%2Fapp%2Fbilling%3Fcheckout%3Dcancel" in seen[1].content
    assert b"unit_amount" not in seen[1].content


@pytest.mark.asyncio
async def test_one_time_price_cannot_start_subscription_checkout() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "object": "price",
                "id": "price_test_contract",
                "livemode": False,
                "active": True,
                "currency": "usd",
                "unit_amount": 1000,
                "type": "one_time",
                "recurring": None,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = StripeSandboxClient(test_secret_key="sk_test_synthetic", client=http_client)
        with pytest.raises(BillingOperationError) as error:
            await client.create_checkout(
                customer_reference="cus_test_contract",
                price_reference="price_test_contract",
                checkout_command_reference=str(uuid4()),
                currency=CurrencyCode.USD,
                amount_minor=1000,
                billing_cycle="monthly",
                return_origin="http://localhost:5173",
                idempotency_key="checkout:synthetic",
            )
    assert error.value.code is BillingErrorCode.CATALOG_VERSION_UNAVAILABLE
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_customer_contains_only_the_internal_organization_reference() -> None:
    organization_id = uuid4()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"object": "customer", "id": "cus_test_contract", "livemode": False})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = StripeSandboxClient(test_secret_key="sk_test_synthetic", client=http_client)
        customer = await client.create_customer(
            organization_reference=str(organization_id), idempotency_key="customer:synthetic"
        )

    assert customer == "cus_test_contract"
    assert seen[0].headers["Idempotency-Key"] == "customer:synthetic"
    assert str(organization_id).encode() in seen[0].content
    assert b"email" not in seen[0].content.lower()


@pytest.mark.asyncio
async def test_sandbox_gateway_creates_a_pending_checkout_without_inventing_a_subscription() -> None:
    command_id = uuid4()
    organization_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/customers":
            return httpx.Response(200, json={"object": "customer", "id": "cus_test_contract", "livemode": False})
        if request.url.path == "/v1/prices/price_test_contract":
            return httpx.Response(
                200,
                json={
                    "object": "price",
                    "id": "price_test_contract",
                    "livemode": False,
                    "active": True,
                    "currency": "xaf",
                    "unit_amount": 5000,
                    "type": "recurring",
                    "recurring": {"interval": "month", "interval_count": 1},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "cs_test_contract",
                "url": "https://checkout.stripe.com/c/pay/cs_test_contract",
                "expires_at": _CREATED + 3600,
                "livemode": False,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        gateway = StripeSandboxProviderGateway(
            client=StripeSandboxClient(test_secret_key="sk_test_synthetic", client=http_client),
            return_origin="http://localhost:5173",
        )
        session = await gateway.create_checkout(
            command=BillingCheckoutCommand(
                organization_id=organization_id,
                plan_version_id=uuid4(),
                currency=CurrencyCode.XAF,
                provider_price_reference="price_test_contract",
                return_target=BillingReturnTarget.SUBSCRIPTION,
                amount_minor=5000,
            ),
            idempotency_key=f"checkout:{command_id}",
        )

    assert session.provider_customer_reference == "cus_test_contract"
    assert session.provider_checkout_reference == "cs_test_contract"
    assert session.provider_subscription_reference is None
    assert session.subscription is None


@pytest.mark.asyncio
async def test_sandbox_gateway_reuses_the_organizations_existing_customer() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/customers":
            raise AssertionError("Un client Stripe déjà enregistré ne doit pas être recréé.")
        if request.url.path == "/v1/prices/price_test_contract":
            return httpx.Response(
                200,
                json={
                    "object": "price",
                    "id": "price_test_contract",
                    "livemode": False,
                    "active": True,
                    "currency": "xaf",
                    "unit_amount": 5000,
                    "type": "recurring",
                    "recurring": {"interval": "month", "interval_count": 1},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "cs_test_reused",
                "url": "https://checkout.stripe.com/c/pay/cs_test_reused",
                "expires_at": _CREATED + 3600,
                "livemode": False,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        gateway = StripeSandboxProviderGateway(
            client=StripeSandboxClient(test_secret_key="sk_test_synthetic", client=http_client),
            return_origin="http://localhost:5173",
        )
        session = await gateway.create_checkout(
            command=BillingCheckoutCommand(
                organization_id=uuid4(),
                plan_version_id=uuid4(),
                currency=CurrencyCode.XAF,
                provider_price_reference="price_test_contract",
                return_target=BillingReturnTarget.SUBSCRIPTION,
                amount_minor=5000,
                provider_customer_reference="cus_test_existing",
            ),
            idempotency_key=f"checkout:{uuid4()}",
        )

    assert session.provider_customer_reference == "cus_test_existing"
    assert [request.url.path for request in requests] == [
        "/v1/prices/price_test_contract",
        "/v1/checkout/sessions",
    ]
    assert b"customer=cus_test_existing" in requests[-1].content


@pytest.mark.asyncio
async def test_xaf_amount_mismatch_is_rejected_without_conversion() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "object": "price",
                "id": "price_test_contract",
                "livemode": False,
                "active": True,
                "currency": "xaf",
                "unit_amount": 500_000,
                "type": "recurring",
                "recurring": {"interval": "month", "interval_count": 1},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = StripeSandboxClient(test_secret_key="sk_test_synthetic", client=http_client)
        with pytest.raises(BillingOperationError) as error:
            await client.get_price(
                "price_test_contract", currency=CurrencyCode.XAF, amount_minor=5000, billing_cycle="monthly"
            )
    assert error.value.code is BillingErrorCode.CATALOG_VERSION_UNAVAILABLE
