"""Simulateur Billing déterministe, local et intégralement hors réseau.

Il implémente le port sortant P5.3 et fabrique des livraisons webhook signées.
L'admission durable, la déduplication en base et la projection appartiennent aux
étapes P53-04 et P53-05 : ce module ne les simule pas et ne touche pas à la DB.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from ...application.errors import BillingOperationError
from ...application.ports.billing import (
    BillingCheckoutCommand,
    BillingEventPage,
    BillingPortalCommand,
    BillingProviderGateway,
    BillingRefundCommand,
    CheckoutSession,
    NormalizedBillingEvent,
    NormalizedSubscriptionSnapshot,
    PortalSession,
)
from ...domain.billing import BillingErrorCode, BillingEventType, BillingPeriod, BillingProvider, SubscriptionState

_WEBHOOK_API_VERSION = "simulated-2026-10-09"
_SESSION_TTL = timedelta(minutes=30)
_SUBSCRIPTION_PERIOD = timedelta(days=30)


class SimulatedWebhookScenario(StrEnum):
    CHECKOUT_COMPLETED = "checkout_completed"
    INVOICE_PAID = "invoice_paid"
    INVOICE_PAYMENT_FAILED = "invoice_payment_failed"
    SUBSCRIPTION_CANCEL_SCHEDULED = "subscription_cancel_scheduled"
    SUBSCRIPTION_CANCELED = "subscription_canceled"
    PAYMENT_RECOVERED = "payment_recovered"
    REFUND_SUCCEEDED = "refund_succeeded"
    DUPLICATE_EVENT = "duplicate_event"
    EVENT_ID_COLLISION = "event_id_collision"
    STALE_EVENT = "stale_event"
    INVALID_SIGNATURE = "invalid_signature"
    EXPIRED_SIGNATURE = "expired_signature"
    PROVIDER_TIMEOUT_BEFORE_EFFECT = "provider_timeout_before_effect"
    PROVIDER_TIMEOUT_AFTER_EFFECT = "provider_timeout_after_effect"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


@dataclass(frozen=True, slots=True)
class SimulatedWebhookDelivery:
    """Enveloppe brute destinée aux seuls tests d'admission P53-04.

    Le corps et la signature ne doivent jamais être journalisés par l'appelant.
    """

    event: NormalizedBillingEvent
    raw_body: bytes
    signature_header: str


@dataclass(frozen=True, slots=True)
class _IdempotentValue:
    fingerprint: str
    value: CheckoutSession | PortalSession | NormalizedBillingEvent


class SimulatedBillingProviderGateway(BillingProviderGateway):
    """Fournisseur en mémoire sans réseau public ni dépendance Stripe.

    Une horloge injectée rend les références, périodes et signatures rejouables.
    Les URL retournées sont des identifiants locaux opaques ; ce module ne tente
    jamais de les résoudre.
    """

    def __init__(
        self,
        *,
        webhook_secret: bytes,
        clock: Callable[[], datetime] | None = None,
        previous_webhook_secret: bytes | None = None,
    ) -> None:
        if len(webhook_secret) < 32:
            raise ValueError("Le secret webhook simulé doit contenir au moins 32 octets.")
        if previous_webhook_secret is not None and len(previous_webhook_secret) < 32:
            raise ValueError("Le secret webhook précédent doit contenir au moins 32 octets.")
        self._webhook_secret = webhook_secret
        self._previous_webhook_secret = previous_webhook_secret
        self._clock = clock or (lambda: datetime.now(UTC))
        self._idempotency: dict[tuple[str, str], _IdempotentValue] = {}
        self._subscriptions: dict[str, NormalizedSubscriptionSnapshot] = {}
        self._events: dict[str, NormalizedBillingEvent] = {}
        self._deliveries: dict[str, SimulatedWebhookDelivery] = {}
        self._checkout_subscriptions: dict[str, str] = {}
        self._next_scenario: SimulatedWebhookScenario | None = None

    def configure_next_scenario(self, scenario: SimulatedWebhookScenario) -> None:
        """Configure un unique appel sortant pour un scénario de panne local."""

        self._next_scenario = scenario

    async def create_checkout(self, *, command: BillingCheckoutCommand, idempotency_key: str) -> CheckoutSession:
        scenario = self._take_outbound_scenario()
        self._raise_if_no_effect(scenario)
        fingerprint = self._checkout_fingerprint(command)
        cached = self._lookup_idempotent("checkout", idempotency_key, fingerprint)
        if cached is not None:
            assert isinstance(cached, CheckoutSession)
            return cached

        now = self._now()
        reference = self._reference("checkout", idempotency_key, fingerprint)
        subscription_reference = self._reference("subscription", reference, command.provider_price_reference)
        customer_reference = self._reference("customer", str(command.organization_id), command.currency.value)
        snapshot = NormalizedSubscriptionSnapshot(
            provider_subscription_reference=subscription_reference,
            provider_customer_reference=customer_reference,
            state=SubscriptionState.PENDING_CHECKOUT,
            currency=command.currency,
            provider_price_reference=command.provider_price_reference,
            period=BillingPeriod(now, now + _SUBSCRIPTION_PERIOD),
            cancel_at_period_end=False,
            provider_updated_at=now,
        )
        self._subscriptions[subscription_reference] = snapshot
        self._checkout_subscriptions[reference] = subscription_reference
        session = CheckoutSession(
            provider_checkout_reference=reference,
            provider_customer_reference=customer_reference,
            provider_subscription_reference=subscription_reference,
            subscription=snapshot,
            checkout_url=f"http://billing-simulator.local/checkout/{reference}",
            expires_at=now + _SESSION_TTL,
        )
        self._remember_idempotent("checkout", idempotency_key, fingerprint, session)
        self._raise_if_effect_unknown(scenario)
        return session

    async def create_portal_session(self, *, command: BillingPortalCommand, idempotency_key: str) -> PortalSession:
        scenario = self._take_outbound_scenario()
        self._raise_if_no_effect(scenario)
        fingerprint = self._portal_fingerprint(command)
        cached = self._lookup_idempotent("portal", idempotency_key, fingerprint)
        if cached is not None:
            assert isinstance(cached, PortalSession)
            return cached

        now = self._now()
        reference = self._reference("portal", idempotency_key, fingerprint)
        session = PortalSession(
            provider_portal_reference=reference,
            portal_url=f"http://billing-simulator.local/portal/{reference}",
            expires_at=now + _SESSION_TTL,
        )
        self._remember_idempotent("portal", idempotency_key, fingerprint, session)
        self._raise_if_effect_unknown(scenario)
        return session

    async def get_subscription(self, *, provider_subscription_reference: str) -> NormalizedSubscriptionSnapshot:
        try:
            return self._subscriptions[provider_subscription_reference]
        except KeyError as error:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN) from error

    async def list_events(
        self, *, cursor: str | None, occurred_from: datetime, occurred_to: datetime
    ) -> BillingEventPage:
        if occurred_from.tzinfo is None or occurred_to.tzinfo is None or occurred_to < occurred_from:
            raise ValueError("La fenêtre d'événements doit être UTC et ordonnée.")
        events = sorted(
            (event for event in self._events.values() if occurred_from <= event.provider_created_at <= occurred_to),
            key=lambda event: (event.provider_created_at, event.provider_event_id),
        )
        start = 0
        if cursor is not None:
            ids = [event.provider_event_id for event in events]
            try:
                start = ids.index(cursor) + 1
            except ValueError as error:
                raise ValueError("Le curseur simulateur est inconnu.") from error
        return BillingEventPage(events=tuple(events[start:]), next_cursor=None)

    async def refund_first_payment(
        self, *, command: BillingRefundCommand, idempotency_key: str
    ) -> NormalizedBillingEvent:
        scenario = self._take_outbound_scenario()
        self._raise_if_no_effect(scenario)
        fingerprint = self._refund_fingerprint(command)
        cached = self._lookup_idempotent("refund", idempotency_key, fingerprint)
        if cached is not None:
            assert isinstance(cached, NormalizedBillingEvent)
            return cached

        now = self._now()
        event = NormalizedBillingEvent(
            provider=BillingProvider.SIMULATED,
            provider_event_id=self._reference("event", "refund", idempotency_key),
            event_type=BillingEventType.REFUND_SUCCEEDED,
            # La référence de paiement demeure opaque et ne sort jamais de l'API.
            # Elle doit toutefois rester joignable à la commande durable lors du webhook.
            provider_object_reference=command.provider_payment_reference,
            provider_created_at=now,
        )
        self._events[event.provider_event_id] = event
        self._remember_idempotent("refund", idempotency_key, fingerprint, event)
        self._raise_if_effect_unknown(scenario)
        return event

    def emit_webhook(self, *, checkout_reference: str, scenario: SimulatedWebhookScenario) -> SimulatedWebhookDelivery:
        """Produit une livraison signée sans l'envoyer sur le réseau.

        Les scénarios timeout/unavailable ciblent une commande sortante et sont
        donc explicitement refusés ici plutôt que de créer un effet ambigu.
        """

        if scenario in {
            SimulatedWebhookScenario.PROVIDER_TIMEOUT_BEFORE_EFFECT,
            SimulatedWebhookScenario.PROVIDER_TIMEOUT_AFTER_EFFECT,
            SimulatedWebhookScenario.PROVIDER_UNAVAILABLE,
        }:
            raise ValueError("Ce scénario doit être configuré avant une commande fournisseur.")
        if scenario is SimulatedWebhookScenario.DUPLICATE_EVENT:
            return self._duplicate_delivery(checkout_reference)
        if scenario is SimulatedWebhookScenario.EVENT_ID_COLLISION:
            return self._colliding_delivery(checkout_reference)

        subscription = self._subscription_for_checkout(checkout_reference)
        event_type, next_state = self._scenario_transition(scenario, subscription.state)
        now = self._now()
        provider_created_at = now - timedelta(minutes=10) if scenario is SimulatedWebhookScenario.STALE_EVENT else now
        updated_subscription = NormalizedSubscriptionSnapshot(
            provider_subscription_reference=subscription.provider_subscription_reference,
            provider_customer_reference=subscription.provider_customer_reference,
            state=next_state,
            currency=subscription.currency,
            provider_price_reference=subscription.provider_price_reference,
            period=subscription.period,
            cancel_at_period_end=next_state is SubscriptionState.CANCELING,
            provider_updated_at=provider_created_at,
        )
        self._subscriptions[updated_subscription.provider_subscription_reference] = updated_subscription
        event = NormalizedBillingEvent(
            provider=BillingProvider.SIMULATED,
            provider_event_id=self._reference("event", checkout_reference, scenario.value),
            event_type=event_type,
            provider_object_reference=updated_subscription.provider_subscription_reference,
            provider_created_at=provider_created_at,
            normalized_subscription=updated_subscription,
        )
        delivery = self._delivery_for(event, received_at=now)
        if scenario is SimulatedWebhookScenario.INVALID_SIGNATURE:
            delivery = SimulatedWebhookDelivery(event, delivery.raw_body, "t=0,v1=invalid")
        elif scenario is SimulatedWebhookScenario.EXPIRED_SIGNATURE:
            delivery = self._delivery_for(event, received_at=now - timedelta(minutes=6))
        self._events[event.provider_event_id] = event
        self._deliveries[checkout_reference] = delivery
        return delivery

    def _take_outbound_scenario(self) -> SimulatedWebhookScenario | None:
        scenario, self._next_scenario = self._next_scenario, None
        return scenario

    @staticmethod
    def _raise_if_no_effect(scenario: SimulatedWebhookScenario | None) -> None:
        if scenario is SimulatedWebhookScenario.PROVIDER_UNAVAILABLE:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE)
        if scenario is SimulatedWebhookScenario.PROVIDER_TIMEOUT_BEFORE_EFFECT:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE)
        if scenario not in {None, SimulatedWebhookScenario.PROVIDER_TIMEOUT_AFTER_EFFECT}:
            raise ValueError("Ce scénario est réservé aux livraisons webhook.")

    @staticmethod
    def _raise_if_effect_unknown(scenario: SimulatedWebhookScenario | None) -> None:
        if scenario is SimulatedWebhookScenario.PROVIDER_TIMEOUT_AFTER_EFFECT:
            raise BillingOperationError(BillingErrorCode.RECONCILIATION_REQUIRED)

    def _duplicate_delivery(self, checkout_reference: str) -> SimulatedWebhookDelivery:
        try:
            return self._deliveries[checkout_reference]
        except KeyError as error:
            raise ValueError("Un événement initial doit être produit avant un doublon.") from error

    def _colliding_delivery(self, checkout_reference: str) -> SimulatedWebhookDelivery:
        original = self._duplicate_delivery(checkout_reference)
        payload = json.loads(original.raw_body)
        payload["data"]["object"]["simulator_collision"] = True
        raw_body = self._canonical_json(payload)
        timestamp = int(self._now().timestamp())
        return SimulatedWebhookDelivery(
            event=original.event,
            raw_body=raw_body,
            signature_header=self._signature_header(raw_body, timestamp),
        )

    def _subscription_for_checkout(self, checkout_reference: str) -> NormalizedSubscriptionSnapshot:
        try:
            subscription_reference = self._checkout_subscriptions[checkout_reference]
            return self._subscriptions[subscription_reference]
        except KeyError as error:
            raise ValueError("La session checkout simulée est inconnue.") from error

    def _scenario_transition(
        self, scenario: SimulatedWebhookScenario, current: SubscriptionState
    ) -> tuple[BillingEventType, SubscriptionState]:
        if scenario is SimulatedWebhookScenario.CHECKOUT_COMPLETED:
            return BillingEventType.CHECKOUT_COMPLETED, current
        if scenario in {SimulatedWebhookScenario.INVOICE_PAID, SimulatedWebhookScenario.PAYMENT_RECOVERED}:
            return BillingEventType.INVOICE_PAID, SubscriptionState.ACTIVE
        if scenario is SimulatedWebhookScenario.INVOICE_PAYMENT_FAILED:
            return BillingEventType.INVOICE_PAYMENT_FAILED, SubscriptionState.PAST_DUE
        if scenario is SimulatedWebhookScenario.SUBSCRIPTION_CANCEL_SCHEDULED:
            return BillingEventType.SUBSCRIPTION_SNAPSHOT, SubscriptionState.CANCELING
        if scenario is SimulatedWebhookScenario.SUBSCRIPTION_CANCELED:
            return BillingEventType.SUBSCRIPTION_SNAPSHOT, SubscriptionState.CANCELED
        if scenario is SimulatedWebhookScenario.REFUND_SUCCEEDED:
            return BillingEventType.REFUND_SUCCEEDED, current
        if scenario in {
            SimulatedWebhookScenario.STALE_EVENT,
            SimulatedWebhookScenario.INVALID_SIGNATURE,
            SimulatedWebhookScenario.EXPIRED_SIGNATURE,
        }:
            return BillingEventType.INVOICE_PAID, SubscriptionState.ACTIVE
        raise ValueError("Le scénario webhook n'est pas reconnu.")

    def _delivery_for(self, event: NormalizedBillingEvent, *, received_at: datetime) -> SimulatedWebhookDelivery:
        timestamp = int(received_at.timestamp())
        payload = {
            "api_version": _WEBHOOK_API_VERSION,
            "created": int(event.provider_created_at.timestamp()),
            "data": {"object": self._event_object(event)},
            "id": event.provider_event_id,
            "type": event.event_type.value,
        }
        raw_body = self._canonical_json(payload)
        return SimulatedWebhookDelivery(event, raw_body, self._signature_header(raw_body, timestamp))

    @staticmethod
    def _event_object(event: NormalizedBillingEvent) -> dict[str, object]:
        snapshot = event.normalized_subscription
        object_data: dict[str, object] = {"reference": event.provider_object_reference}
        if snapshot is not None:
            object_data["subscription"] = {
                "cancel_at_period_end": snapshot.cancel_at_period_end,
                "currency": snapshot.currency.value,
                "current_period_end": snapshot.period.ends_at.isoformat(),
                "current_period_start": snapshot.period.starts_at.isoformat(),
                "customer_reference": snapshot.provider_customer_reference,
                "price_reference": snapshot.provider_price_reference,
                "reference": snapshot.provider_subscription_reference,
                "state": snapshot.state.value,
                "updated_at": snapshot.provider_updated_at.isoformat(),
            }
        return object_data

    def _lookup_idempotent(
        self, kind: str, idempotency_key: str, fingerprint: str
    ) -> CheckoutSession | PortalSession | NormalizedBillingEvent | None:
        if not idempotency_key.strip():
            raise ValueError("La clé d'idempotence est obligatoire.")
        existing = self._idempotency.get((kind, idempotency_key))
        if existing is None:
            return None
        if not hmac.compare_digest(existing.fingerprint, fingerprint):
            raise BillingOperationError(BillingErrorCode.COMMAND_CONFLICT)
        return existing.value

    def _remember_idempotent(
        self,
        kind: str,
        idempotency_key: str,
        fingerprint: str,
        value: CheckoutSession | PortalSession | NormalizedBillingEvent,
    ) -> None:
        self._idempotency[(kind, idempotency_key)] = _IdempotentValue(fingerprint, value)

    def _signature_header(self, raw_body: bytes, timestamp: int) -> str:
        signed_payload = str(timestamp).encode("ascii") + b"." + raw_body
        signature = hmac.new(self._webhook_secret, signed_payload, hashlib.sha256).hexdigest()
        return f"t={timestamp},v1={signature}"

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("L'horloge du simulateur doit être UTC.")
        return now.astimezone(UTC)

    @staticmethod
    def _canonical_json(value: dict[str, object]) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

    @staticmethod
    def _reference(*parts: str) -> str:
        material = "\x1f".join(parts).encode("utf-8")
        return f"sim_{hashlib.sha256(material).hexdigest()[:32]}"

    @staticmethod
    def _checkout_fingerprint(command: BillingCheckoutCommand) -> str:
        return "|".join(
            (
                str(command.organization_id),
                str(command.plan_version_id),
                command.currency.value,
                command.provider_price_reference,
                command.return_target.value,
            )
        )

    @staticmethod
    def _portal_fingerprint(command: BillingPortalCommand) -> str:
        return "|".join(
            (str(command.organization_id), command.provider_customer_reference, command.return_target.value)
        )

    @staticmethod
    def _refund_fingerprint(command: BillingRefundCommand) -> str:
        return "|".join((str(command.organization_id), command.provider_payment_reference))
