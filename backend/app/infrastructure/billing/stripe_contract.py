"""Contrat d'événements Stripe sandbox, épinglé et sans effet réseau.

Les objets Stripe sont traités comme des données non fiables même après
vérification de signature. La projection ne reçoit qu'un événement minimal.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ...application.errors import BillingOperationError
from ...application.ports.billing import BillingWebhookVerifier, NormalizedBillingEvent, NormalizedSubscriptionSnapshot
from ...domain.billing import BillingErrorCode, BillingEventType, BillingPeriod, BillingProvider, SubscriptionState
from ...domain.catalog import CurrencyCode

# Stripe CLI uses the test account's default version for local forwarding.
# This value was observed from the P53-09 sandbox listener on 2026-10-24.
STRIPE_API_VERSION = "2025-08-27.basil"
STRIPE_PLANNED_WEBHOOK_EVENTS = (
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
    "refund.updated",
)
_SUBSCRIPTION_EVENTS = frozenset(STRIPE_PLANNED_WEBHOOK_EVENTS[1:4])


class StripeSandboxWebhookVerifier(BillingWebhookVerifier):
    def __init__(self, *, secret: str, tolerance_seconds: int, previous_secret: str = "") -> None:
        if not secret.startswith("whsec_") or (previous_secret and not previous_secret.startswith("whsec_")):
            raise ValueError("Un secret de signature Stripe est requis.")
        self._secrets = (secret,) + ((previous_secret,) if previous_secret else ())
        self._tolerance_seconds = tolerance_seconds

    def verify(self, *, raw_body: bytes, signature_header: str, received_at: datetime) -> NormalizedBillingEvent:
        if received_at.tzinfo is None or received_at.utcoffset() is None:
            raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID)
        parts: dict[str, list[str]] = {}
        for fragment in signature_header.split(","):
            key, separator, value = fragment.strip().partition("=")
            if separator:
                parts.setdefault(key, []).append(value)
        timestamps = parts.get("t", [])
        signatures = parts.get("v1", [])
        if len(timestamps) != 1 or not timestamps[0].isdecimal() or not signatures:
            raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID)
        timestamp = int(timestamps[0])
        if abs(int(received_at.astimezone(UTC).timestamp()) - timestamp) > self._tolerance_seconds:
            raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID)
        signed = timestamps[0].encode("ascii") + b"." + raw_body
        if not any(
            hmac.compare_digest(hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest(), signature)
            for secret in self._secrets
            for signature in signatures
        ):
            raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID)
        try:
            return normalize_stripe_event(json.loads(raw_body))
        except (ValueError, TypeError, UnicodeDecodeError) as error:
            raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID) from error


def normalize_stripe_event(payload: Any) -> NormalizedBillingEvent:
    """Shared by authenticated API replay and signed admission; never persists PII."""
    try:
        if not isinstance(payload, dict) or payload.get("livemode") is not False:
            raise ValueError
        if payload.get("api_version") != STRIPE_API_VERSION:
            raise BillingOperationError(BillingErrorCode.WEBHOOK_UNSUPPORTED)
        kind = payload.get("type")
        if kind not in STRIPE_PLANNED_WEBHOOK_EVENTS:
            raise BillingOperationError(BillingErrorCode.WEBHOOK_UNSUPPORTED)
        obj = payload["data"]["object"]
        if not isinstance(obj, dict):
            raise ValueError
        expected, prefix, event_type = {
            "checkout.session.completed": ("checkout.session", "cs_test_", BillingEventType.CHECKOUT_COMPLETED),
            "invoice.paid": ("invoice", "in_", BillingEventType.INVOICE_PAID),
            "invoice.payment_failed": ("invoice", "in_", BillingEventType.INVOICE_PAYMENT_FAILED),
            "refund.updated": ("refund", "re_", BillingEventType.REFUND_UPDATED),
        }.get(kind, ("subscription", "sub_", BillingEventType.SUBSCRIPTION_SNAPSHOT))
        if obj.get("object") != expected or (expected != "refund" and obj.get("livemode") is not False):
            raise ValueError
        if expected == "refund" and obj.get("livemode", False) is not False:
            raise ValueError
        created = _timestamp(payload["created"])
        return NormalizedBillingEvent(
            provider=BillingProvider.STRIPE,
            provider_event_id=_reference(payload["id"], "evt_"),
            event_type=event_type,
            provider_object_reference=_reference(obj["id"], prefix),
            provider_created_at=created,
            normalized_subscription=subscription_snapshot_from_object(obj, created)
            if kind in _SUBSCRIPTION_EVENTS
            else None,
            checkout_command_id=_checkout_command_id(obj) if kind in _SUBSCRIPTION_EVENTS else None,
            provider_event_kind=kind,
        )
    except BillingOperationError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID) from error


def subscription_snapshot_from_object(obj: dict[str, Any], created_at: datetime) -> NormalizedSubscriptionSnapshot:
    if obj.get("object") != "subscription":
        raise ValueError
    items = obj["items"]["data"]
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise ValueError
    item = items[0]
    price = item["price"]
    if not isinstance(price, dict):
        raise ValueError
    currency = CurrencyCode(_reference(price["currency"]).upper())
    if currency.value.lower() != obj["currency"] or price.get("recurring") is None:
        raise ValueError
    if not isinstance(obj["cancel_at_period_end"], bool):
        raise ValueError
    status = obj["status"]
    if status == "canceled":
        state = SubscriptionState.CANCELED
    elif status == "active" and obj["cancel_at_period_end"]:
        state = SubscriptionState.CANCELING
    elif status in {"active", "past_due", "unpaid", "incomplete", "incomplete_expired"}:
        state = {
            "active": SubscriptionState.ACTIVE,
            "past_due": SubscriptionState.PAST_DUE,
            "unpaid": SubscriptionState.SUSPENDED,
            "incomplete": SubscriptionState.PENDING_CHECKOUT,
            "incomplete_expired": SubscriptionState.CANCELED,
        }[status]
    else:
        raise ValueError
    return NormalizedSubscriptionSnapshot(
        provider_subscription_reference=_reference(obj["id"], "sub_"),
        provider_customer_reference=_reference(obj["customer"], "cus_"),
        state=state,
        currency=currency,
        provider_price_reference=_reference(price["id"], "price_"),
        period=BillingPeriod(_timestamp(item["current_period_start"]), _timestamp(item["current_period_end"])),
        cancel_at_period_end=obj["cancel_at_period_end"],
        provider_updated_at=created_at,
    )


def _reference(value: object, prefix: str = "") -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 255
        or not value.startswith(prefix)
        or not value.isascii()
        or not value.replace("_", "").isalnum()
    ):
        raise ValueError
    return value


def _checkout_command_id(subscription: dict[str, Any]) -> UUID | None:
    metadata = subscription.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError
    value = metadata.get("billing_command_id")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError
    return UUID(value)


def _timestamp(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError
    return datetime.fromtimestamp(value, UTC)
