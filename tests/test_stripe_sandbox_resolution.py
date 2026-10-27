"""Provider evidence must belong to the same subscription, price and period."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest

from backend.app.application.errors import BillingOperationError
from backend.app.domain.billing import BillingErrorCode, BillingEventType
from backend.app.infrastructure.billing.stripe_contract import STRIPE_API_VERSION, normalize_stripe_event
from backend.app.infrastructure.billing.stripe_resolution import StripeEventResolver

START = 1793000000
END = START + 2592000
COMMAND = str(uuid4())


def objects(status: str = "paid") -> dict[tuple[str, str], dict]:
    subscription = {
        "id": "sub_test123",
        "object": "subscription",
        "livemode": False,
        "customer": "cus_test123",
        "currency": "xaf",
        "status": "active",
        "cancel_at_period_end": False,
        "metadata": {"billing_command_id": COMMAND},
        "created": START,
        "latest_invoice": "in_test123",
        "items": {
            "data": [
                {
                    "current_period_start": START,
                    "current_period_end": END,
                    "price": {"id": "price_test123", "currency": "xaf", "recurring": {"interval": "month"}},
                }
            ]
        },
    }
    invoice = {
        "id": "in_test123",
        "object": "invoice",
        "livemode": False,
        "customer": "cus_test123",
        "currency": "xaf",
        "status": status,
        "amount_due": 5000,
        "amount_paid": 5000 if status == "paid" else 0,
        "amount_remaining": 0 if status == "paid" else 5000,
        "parent": {"type": "subscription_details", "subscription_details": {"subscription": "sub_test123"}},
        "lines": {
            "has_more": False,
            "data": [
                {
                    "amount": 5000,
                    "currency": "xaf",
                    "quantity": 1,
                    "period": {"start": START, "end": END},
                    "parent": {
                        "type": "subscription_item_details",
                        "subscription_item_details": {"subscription": "sub_test123", "proration": False},
                    },
                    "pricing": {"price_details": {"price": "price_test123"}},
                }
            ],
        },
    }
    return {("subscription", "sub_test123"): subscription, ("invoice", "in_test123"): invoice}


class StubClient:
    def __init__(self, data: dict[tuple[str, str], dict]) -> None:
        self.data = data

    async def read_object(self, kind: str, reference: str) -> dict:
        return self.data[(kind, reference)]

    async def invoice_for_payment(self, reference: str) -> dict:
        if reference != "pi_test123":
            raise AssertionError("unexpected payment")
        return self.data[("invoice", "in_test123")]


@pytest.mark.asyncio
async def test_resolver_requires_paid_invoice_for_current_period() -> None:
    paid = await StripeEventResolver(StubClient(objects())).resolve(
        {"provider_event_kind": "invoice.paid", "provider_object_reference": "in_test123"}
    )
    assert paid["invoice"]["paid"] is True
    assert paid["invoice"]["amount_minor"] == 5000
    assert paid["checkout_command_id"] == COMMAND
    assert paid["subscription"]["state"] == "active"

    unpaid = await StripeEventResolver(StubClient(objects("open"))).resolve(
        {"provider_event_kind": "customer.subscription.updated", "provider_object_reference": "sub_test123"}
    )
    assert unpaid["subscription"]["state"] == "active"
    assert unpaid["invoice"]["paid"] is False


@pytest.mark.asyncio
async def test_resolver_rejects_cross_subscription_and_wrong_price() -> None:
    for field, value in (("subscription", "sub_other"), ("price", "price_other")):
        data = deepcopy(objects())
        if field == "subscription":
            data[("invoice", "in_test123")]["parent"]["subscription_details"]["subscription"] = value
        else:
            data[("invoice", "in_test123")]["lines"]["data"][0]["pricing"]["price_details"]["price"] = value
        with pytest.raises(BillingOperationError) as error:
            await StripeEventResolver(StubClient(data)).resolve(
                {"provider_event_kind": "invoice.paid", "provider_object_reference": "in_test123"}
            )
        assert error.value.code is BillingErrorCode.STATE_UNKNOWN


@pytest.mark.asyncio
async def test_checkout_evidence_requires_matching_customer_and_command() -> None:
    data = objects()
    data[("checkout", "cs_test_123")] = {
        "id": "cs_test_123",
        "object": "checkout.session",
        "livemode": False,
        "mode": "subscription",
        "status": "complete",
        "subscription": "sub_test123",
        "customer": "cus_test123",
        "currency": "xaf",
        "client_reference_id": COMMAND,
    }
    payload = {"provider_event_kind": "checkout.session.completed", "provider_object_reference": "cs_test_123"}
    evidence = await StripeEventResolver(StubClient(data)).resolve(payload)
    assert evidence["checkout_reference"] == "cs_test_123"
    assert evidence["checkout_command_id"] == COMMAND
    data[("checkout", "cs_test_123")]["client_reference_id"] = str(uuid4())
    with pytest.raises(BillingOperationError):
        await StripeEventResolver(StubClient(data)).resolve(payload)


@pytest.mark.asyncio
async def test_refund_evidence_is_bound_to_paid_invoice_and_test_charge() -> None:
    data = objects()
    data[("refund", "re_test123")] = {
        "id": "re_test123",
        "object": "refund",
        "charge": "ch_test123",
        "payment_intent": "pi_test123",
        "currency": "xaf",
        "amount": 5000,
        "status": "succeeded",
    }
    data[("charge", "ch_test123")] = {
        "id": "ch_test123",
        "object": "charge",
        "livemode": False,
        "payment_intent": "pi_test123",
        "currency": "xaf",
        "customer": "cus_test123",
        "amount": 5000,
    }
    payload = {"provider_event_kind": "refund.updated", "provider_object_reference": "re_test123"}
    evidence = await StripeEventResolver(StubClient(data)).resolve(payload)
    assert evidence["refund"] == {
        "reference": "re_test123",
        "status": "succeeded",
        "amount_minor": 5000,
        "invoice_reference": "in_test123",
    }
    data[("charge", "ch_test123")]["customer"] = "cus_other"
    with pytest.raises(BillingOperationError):
        await StripeEventResolver(StubClient(data)).resolve(payload)


@pytest.mark.parametrize(
    "kind,object_type,reference,expected",
    [
        ("checkout.session.completed", "checkout.session", "cs_test_123", BillingEventType.CHECKOUT_COMPLETED),
        ("invoice.paid", "invoice", "in_test123", BillingEventType.INVOICE_PAID),
        ("invoice.payment_failed", "invoice", "in_test123", BillingEventType.INVOICE_PAYMENT_FAILED),
        ("refund.updated", "refund", "re_test123", BillingEventType.REFUND_UPDATED),
    ],
)
def test_planned_events_admit_only_opaque_reference(
    kind: str, object_type: str, reference: str, expected: BillingEventType
) -> None:
    event = normalize_stripe_event(
        {
            "id": "evt_test123",
            "api_version": STRIPE_API_VERSION,
            "livemode": False,
            "created": START,
            "type": kind,
            "data": {
                "object": {
                    "id": reference,
                    "object": object_type,
                    "livemode": False,
                    "customer_email": "excluded@example.test",
                }
            },
        }
    )
    assert event.event_type is expected
    assert event.provider_event_kind == kind
    assert event.normalized_subscription is None
    assert "customer_email" not in repr(event)
