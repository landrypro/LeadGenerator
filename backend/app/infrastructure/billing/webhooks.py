"""Admission P53-04 des webhooks Billing, sans projection d'abonnement.

Le vérificateur travaille exclusivement sur le corps brut.  Le service ne
renvoie ni corps, ni signature, ni référence fournisseur dans ses erreurs.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ...application.errors import BillingOperationError
from ...application.ports.billing import (
    BillingEventInbox,
    BillingWebhookAdmissionCode,
    BillingWebhookVerifier,
    NormalizedBillingEvent,
    NormalizedSubscriptionSnapshot,
)
from ...domain.billing import (
    BillingErrorCode,
    BillingEventType,
    BillingPeriod,
    BillingProvider,
    SubscriptionState,
)
from ...domain.catalog import CurrencyCode

SIMULATED_WEBHOOK_API_VERSION = "simulated-2026-10-09"
MAX_WEBHOOK_BODY_BYTES = 64 * 1024


class SimulatedBillingWebhookVerifier(BillingWebhookVerifier):
    """Vérifie HMAC/tolérance avant toute désérialisation JSON."""

    def __init__(
        self,
        *,
        current_secret: bytes,
        tolerance_seconds: int,
        previous_secret: bytes | None = None,
    ) -> None:
        self._current_secret = current_secret
        self._previous_secret = previous_secret
        self._tolerance_seconds = tolerance_seconds

    def verify(self, *, raw_body: bytes, signature_header: str, received_at: datetime) -> NormalizedBillingEvent:
        timestamp, signature = self._signature_parts(signature_header)
        now = self._utc(received_at)
        if abs(int(now.timestamp()) - timestamp) > self._tolerance_seconds:
            raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID)
        signed_payload = str(timestamp).encode("ascii") + b"." + raw_body
        candidates = (self._current_secret,) + ((self._previous_secret,) if self._previous_secret else ())
        if not any(
            hmac.compare_digest(hmac.new(secret, signed_payload, hashlib.sha256).hexdigest(), signature)
            for secret in candidates
        ):
            raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID)
        return self._parse(raw_body)

    @staticmethod
    def _signature_parts(value: str) -> tuple[int, str]:
        raw_parts = [part.split("=", 1) for part in value.split(",") if part.count("=") == 1]
        pieces = dict(raw_parts)
        timestamp_text = pieces.get("t", "")
        signature = pieces.get("v1", "")
        if (
            len(raw_parts) != 2
            or len(pieces) != 2
            or set(pieces) != {"t", "v1"}
            or not timestamp_text.isdecimal()
            or len(signature) != 64
        ):
            raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID)
        try:
            int(signature, 16)
            return int(timestamp_text), signature.lower()
        except ValueError as error:
            raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID) from error

    def _parse(self, raw_body: bytes) -> NormalizedBillingEvent:
        try:
            payload = json.loads(raw_body.decode("utf-8"))
            if not isinstance(payload, dict) or set(payload) != {"api_version", "created", "data", "id", "type"}:
                raise ValueError
            if payload["api_version"] != SIMULATED_WEBHOOK_API_VERSION:
                raise BillingOperationError(BillingErrorCode.WEBHOOK_UNSUPPORTED)
            try:
                event_type = BillingEventType(payload["type"])
            except ValueError as error:
                raise BillingOperationError(BillingErrorCode.WEBHOOK_UNSUPPORTED) from error
            event_id = self._reference(payload["id"])
            created = self._timestamp(payload["created"])
            data = payload["data"]
            if not isinstance(data, dict) or set(data) != {"object"} or not isinstance(data["object"], dict):
                raise ValueError
            object_data = data["object"]
            if set(object_data) - {"reference", "subscription"} or "reference" not in object_data:
                raise ValueError
            snapshot = self._snapshot(object_data.get("subscription"))
            return NormalizedBillingEvent(
                provider=BillingProvider.SIMULATED,
                provider_event_id=event_id,
                event_type=event_type,
                provider_object_reference=self._reference(object_data["reference"]),
                provider_created_at=created,
                normalized_subscription=snapshot,
            )
        except BillingOperationError:
            raise
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID) from error

    def _snapshot(self, value: object) -> NormalizedSubscriptionSnapshot | None:
        if value is None:
            return None
        if not isinstance(value, dict) or set(value) != {
            "cancel_at_period_end",
            "currency",
            "current_period_end",
            "current_period_start",
            "customer_reference",
            "price_reference",
            "reference",
            "state",
            "updated_at",
        }:
            raise ValueError
        if not isinstance(value["cancel_at_period_end"], bool):
            raise ValueError
        return NormalizedSubscriptionSnapshot(
            provider_subscription_reference=self._reference(value["reference"]),
            provider_customer_reference=self._reference(value["customer_reference"]),
            state=SubscriptionState(value["state"]),
            currency=CurrencyCode(value["currency"]),
            provider_price_reference=self._reference(value["price_reference"]),
            period=BillingPeriod(
                self._iso_time(value["current_period_start"]), self._iso_time(value["current_period_end"])
            ),
            cancel_at_period_end=value["cancel_at_period_end"],
            provider_updated_at=self._iso_time(value["updated_at"]),
        )

    @staticmethod
    def _reference(value: object) -> str:
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 255:
            raise ValueError
        return value.strip()

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError
        return datetime.fromtimestamp(value, UTC)

    @staticmethod
    def _iso_time(value: object) -> datetime:
        if not isinstance(value, str):
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return SimulatedBillingWebhookVerifier._utc(parsed)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError
        return value.astimezone(UTC)


class BillingWebhookAdmissionService:
    """Chaîne pure : vérifier, empreinter, puis admettre durablement."""

    def __init__(
        self, verifier: BillingWebhookVerifier, inbox: BillingEventInbox, *, clock: Callable[[], datetime]
    ) -> None:
        self._verifier = verifier
        self._inbox = inbox
        self._clock = clock

    async def admit(self, *, raw_body: bytes, signature_header: str) -> BillingWebhookAdmissionCode:
        if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
            raise BillingOperationError(BillingErrorCode.WEBHOOK_INVALID)
        event = self._verifier.verify(raw_body=raw_body, signature_header=signature_header, received_at=self._clock())
        return await self._inbox.admit(event=event, payload_digest=hashlib.sha256(raw_body).hexdigest())


def normalized_event_payload(event: NormalizedBillingEvent) -> dict[str, Any]:
    """Projection minimale et bornée, sans conserver le corps original."""

    payload: dict[str, Any] = {"schema_version": 1, "provider_object_reference": event.provider_object_reference}
    snapshot = event.normalized_subscription
    if snapshot is not None:
        payload["subscription"] = {
            "reference": snapshot.provider_subscription_reference,
            "customer_reference": snapshot.provider_customer_reference,
            "state": snapshot.state.value,
            "currency": snapshot.currency.value,
            "price_reference": snapshot.provider_price_reference,
            "current_period_start": snapshot.period.starts_at.isoformat(),
            "current_period_end": snapshot.period.ends_at.isoformat(),
            "cancel_at_period_end": snapshot.cancel_at_period_end,
            "updated_at": snapshot.provider_updated_at.isoformat(),
        }
    return payload
