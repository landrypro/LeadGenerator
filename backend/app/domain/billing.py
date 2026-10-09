"""Registres et règles métier fermés du lot P53-01.

Ce module reste indépendant de PostgreSQL, HTTP et de tout SDK fournisseur.
Il ne peut ni émettre un paiement ni activer un fournisseur externe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final


class BillingValidationError(ValueError):
    """Une donnée du domaine de facturation ne respecte pas son contrat fermé."""


class SubscriptionTransitionError(BillingValidationError):
    """La machine d'états refuse la transition demandée."""


class BillingProvider(StrEnum):
    """Fournisseurs connus par le domaine, sans détail de leur SDK."""

    SIMULATED = "simulated"
    STRIPE = "stripe"


class BillingProviderMode(StrEnum):
    """Modes explicitement autorisés par les décisions P5.3.

    Un mode de paiement réel n'est volontairement pas présent dans ce registre.
    """

    DISABLED = "disabled"
    SIMULATED = "simulated"
    STRIPE_SANDBOX = "stripe_sandbox"

    @property
    def allows_provider_commands(self) -> bool:
        return self is not BillingProviderMode.DISABLED

    @property
    def provider(self) -> BillingProvider | None:
        if self is BillingProviderMode.SIMULATED:
            return BillingProvider.SIMULATED
        if self is BillingProviderMode.STRIPE_SANDBOX:
            return BillingProvider.STRIPE
        return None


class SubscriptionState(StrEnum):
    PENDING_CHECKOUT = "pending_checkout"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    GRACE_PERIOD = "grace_period"
    SUSPENDED = "suspended"
    CANCELING = "canceling"
    CANCELED = "canceled"


class SubscriptionTransitionTrigger(StrEnum):
    INVOICE_PAID = "invoice_paid"
    CHECKOUT_ABANDONED = "checkout_abandoned"
    PAYMENT_FAILED = "payment_failed"
    GRACE_PERIOD_STARTED = "grace_period_started"
    GRACE_PERIOD_EXPIRED = "grace_period_expired"
    CANCELLATION_SCHEDULED = "cancellation_scheduled"
    CANCELLATION_REVOKED = "cancellation_revoked"
    CANCELLATION_CONFIRMED = "cancellation_confirmed"
    NEW_CHECKOUT = "new_checkout"


class BillingEventType(StrEnum):
    """Événements normalisés, indépendants des noms Stripe."""

    CHECKOUT_COMPLETED = "checkout.completed"
    SUBSCRIPTION_SNAPSHOT = "subscription.snapshot"
    INVOICE_PAID = "invoice.paid"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
    REFUND_SUCCEEDED = "refund.succeeded"


class BillingErrorCode(StrEnum):
    CAPABILITY_REQUIRED = "billing_capability_required"
    PROVIDER_DISABLED = "billing_provider_disabled"
    PROVIDER_UNAVAILABLE = "billing_provider_unavailable"
    CATALOG_VERSION_UNAVAILABLE = "billing_catalog_version_unavailable"
    CURRENCY_UNAVAILABLE = "billing_currency_unavailable"
    SEAT_LIMIT_CONFLICT = "billing_seat_limit_conflict"
    COMMAND_CONFLICT = "billing_command_conflict"
    VERSION_CONFLICT = "billing_version_conflict"
    SUBSCRIPTION_EXISTS = "billing_subscription_exists"
    WEBHOOK_INVALID = "billing_webhook_invalid"
    WEBHOOK_UNSUPPORTED = "billing_webhook_unsupported"
    EVENT_COLLISION = "billing_event_collision"
    STATE_UNKNOWN = "billing_state_unknown"
    REFUND_NOT_ELIGIBLE = "billing_refund_not_eligible"
    RECONCILIATION_REQUIRED = "billing_reconciliation_required"

    @property
    def http_status(self) -> int:
        return BILLING_ERROR_HTTP_STATUS[self]


BILLING_ERROR_HTTP_STATUS: Final[dict[BillingErrorCode, int]] = {
    BillingErrorCode.CAPABILITY_REQUIRED: 403,
    BillingErrorCode.PROVIDER_DISABLED: 503,
    BillingErrorCode.PROVIDER_UNAVAILABLE: 503,
    BillingErrorCode.CATALOG_VERSION_UNAVAILABLE: 422,
    BillingErrorCode.CURRENCY_UNAVAILABLE: 422,
    BillingErrorCode.SEAT_LIMIT_CONFLICT: 422,
    BillingErrorCode.COMMAND_CONFLICT: 409,
    BillingErrorCode.VERSION_CONFLICT: 409,
    BillingErrorCode.SUBSCRIPTION_EXISTS: 409,
    BillingErrorCode.WEBHOOK_INVALID: 400,
    BillingErrorCode.WEBHOOK_UNSUPPORTED: 422,
    BillingErrorCode.EVENT_COLLISION: 409,
    BillingErrorCode.STATE_UNKNOWN: 503,
    BillingErrorCode.REFUND_NOT_ELIGIBLE: 422,
    BillingErrorCode.RECONCILIATION_REQUIRED: 409,
}


_NEXT_SUBSCRIPTION_STATES: Final[dict[tuple[SubscriptionState, SubscriptionTransitionTrigger], SubscriptionState]] = {
    (SubscriptionState.PENDING_CHECKOUT, SubscriptionTransitionTrigger.INVOICE_PAID): SubscriptionState.ACTIVE,
    (SubscriptionState.PENDING_CHECKOUT, SubscriptionTransitionTrigger.CHECKOUT_ABANDONED): SubscriptionState.CANCELED,
    (SubscriptionState.ACTIVE, SubscriptionTransitionTrigger.PAYMENT_FAILED): SubscriptionState.PAST_DUE,
    (SubscriptionState.PAST_DUE, SubscriptionTransitionTrigger.INVOICE_PAID): SubscriptionState.ACTIVE,
    (SubscriptionState.PAST_DUE, SubscriptionTransitionTrigger.GRACE_PERIOD_STARTED): SubscriptionState.GRACE_PERIOD,
    (SubscriptionState.GRACE_PERIOD, SubscriptionTransitionTrigger.INVOICE_PAID): SubscriptionState.ACTIVE,
    (SubscriptionState.GRACE_PERIOD, SubscriptionTransitionTrigger.GRACE_PERIOD_EXPIRED): SubscriptionState.SUSPENDED,
    (SubscriptionState.SUSPENDED, SubscriptionTransitionTrigger.INVOICE_PAID): SubscriptionState.ACTIVE,
    (SubscriptionState.ACTIVE, SubscriptionTransitionTrigger.CANCELLATION_SCHEDULED): SubscriptionState.CANCELING,
    (SubscriptionState.PAST_DUE, SubscriptionTransitionTrigger.CANCELLATION_SCHEDULED): SubscriptionState.CANCELING,
    (SubscriptionState.CANCELING, SubscriptionTransitionTrigger.CANCELLATION_REVOKED): SubscriptionState.ACTIVE,
    (SubscriptionState.CANCELING, SubscriptionTransitionTrigger.CANCELLATION_CONFIRMED): SubscriptionState.CANCELED,
    (SubscriptionState.CANCELED, SubscriptionTransitionTrigger.NEW_CHECKOUT): SubscriptionState.PENDING_CHECKOUT,
}


def next_subscription_state(current: SubscriptionState, trigger: SubscriptionTransitionTrigger) -> SubscriptionState:
    """Retourne le prochain état ou refuse toute transition hors registre."""

    try:
        return _NEXT_SUBSCRIPTION_STATES[(current, trigger)]
    except KeyError as error:
        raise SubscriptionTransitionError("La transition d'abonnement est invalide.") from error


@dataclass(frozen=True, slots=True)
class SubscriptionTransition:
    """Transition validée et sérialisable pour le futur historique append-only."""

    previous_state: SubscriptionState
    trigger: SubscriptionTransitionTrigger
    next_state: SubscriptionState

    def __post_init__(self) -> None:
        if next_subscription_state(self.previous_state, self.trigger) is not self.next_state:
            raise SubscriptionTransitionError("La transition d'abonnement est incohérente.")


@dataclass(frozen=True, slots=True)
class BillingPeriod:
    """Période fournisseur UTC dont la borne de fin est strictement postérieure."""

    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        if self.starts_at.tzinfo is None or self.starts_at.utcoffset() is None:
            raise BillingValidationError("Le début de période doit être horodaté.")
        if self.ends_at.tzinfo is None or self.ends_at.utcoffset() is None:
            raise BillingValidationError("La fin de période doit être horodatée.")
        if self.ends_at <= self.starts_at:
            raise BillingValidationError("La fin de période doit être postérieure au début.")
