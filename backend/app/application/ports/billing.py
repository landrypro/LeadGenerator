"""Ports de facturation P53-01, sans dépendance à Stripe ni à HTTP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from ...domain.billing import BillingErrorCode, BillingEventType, BillingPeriod, BillingProvider, SubscriptionState
from ...domain.catalog import CurrencyCode
from ..tenancy import ActorContext, TenantContext


class BillingCommandKind(StrEnum):
    CHECKOUT = "checkout"
    PORTAL = "portal"
    REFUND = "refund"


class BillingReturnTarget(StrEnum):
    """Cibles de retour internes : aucune URL arbitraire ne traverse le port."""

    SUBSCRIPTION = "subscription"


class BillingCommandReservationCode(StrEnum):
    RESERVED = "reserved"
    REPLAYED = "replayed"
    CONFLICT = "conflict"


class BillingCommandState(StrEnum):
    RESERVED = "reserved"
    SUCCEEDED = "succeeded"
    UNKNOWN = "unknown"
    FAILED = "failed"


class BillingWebhookAdmissionCode(StrEnum):
    ADMITTED = "admitted"
    DUPLICATE = "duplicate"
    COLLISION = "collision"


class BillingReconciliationDifferenceCode(StrEnum):
    IN_SYNC = "in_sync"
    LOCAL_STALE = "local_stale"
    PROVIDER_STALE = "provider_stale"
    MAPPING_MISSING = "mapping_missing"
    CURRENCY_MISMATCH = "currency_mismatch"
    PRICE_MISMATCH = "price_mismatch"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class BillingCheckoutCommand:
    organization_id: UUID
    plan_version_id: UUID
    currency: CurrencyCode
    provider_price_reference: str
    return_target: BillingReturnTarget
    amount_minor: int = 0
    billing_cycle: str = "monthly"
    provider_customer_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_price_reference.strip():
            raise ValueError("La référence de prix fournisseur est obligatoire.")
        if self.amount_minor < 0 or self.billing_cycle not in {"monthly", "annual"}:
            raise ValueError("Le contrat de prix fournisseur est invalide.")
        if self.provider_customer_reference is not None and not self.provider_customer_reference.strip():
            raise ValueError("La référence client fournisseur est invalide.")


@dataclass(frozen=True, slots=True)
class BillingPortalCommand:
    organization_id: UUID
    provider_customer_reference: str
    return_target: BillingReturnTarget

    def __post_init__(self) -> None:
        if not self.provider_customer_reference.strip():
            raise ValueError("La référence client fournisseur est obligatoire.")


@dataclass(frozen=True, slots=True)
class BillingRefundCommand:
    organization_id: UUID
    provider_payment_reference: str

    def __post_init__(self) -> None:
        if not self.provider_payment_reference.strip():
            raise ValueError("La référence de paiement fournisseur est obligatoire.")


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    """Résultat minimal : la vraie URL demeure éphémère et non journalisable."""

    provider_checkout_reference: str
    provider_customer_reference: str
    provider_subscription_reference: str | None
    subscription: NormalizedSubscriptionSnapshot | None
    checkout_url: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PortalSession:
    provider_portal_reference: str
    portal_url: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class NormalizedSubscriptionSnapshot:
    provider_subscription_reference: str
    provider_customer_reference: str
    state: SubscriptionState
    currency: CurrencyCode
    provider_price_reference: str
    period: BillingPeriod
    cancel_at_period_end: bool
    provider_updated_at: datetime


@dataclass(frozen=True, slots=True)
class NormalizedBillingEvent:
    provider: BillingProvider
    provider_event_id: str
    event_type: BillingEventType
    provider_object_reference: str
    provider_created_at: datetime
    normalized_subscription: NormalizedSubscriptionSnapshot | None = None
    checkout_command_id: UUID | None = None
    provider_event_kind: str | None = None


@dataclass(frozen=True, slots=True)
class BillingEventPage:
    events: tuple[NormalizedBillingEvent, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class BillingCommandReservation:
    code: BillingCommandReservationCode
    command_id: UUID


@dataclass(frozen=True, slots=True)
class BillingCheckoutPreparation:
    command_id: UUID
    state: BillingCommandState
    command: BillingCheckoutCommand


@dataclass(frozen=True, slots=True)
class BillingPortalPreparation:
    command_id: UUID
    state: BillingCommandState
    command: BillingPortalCommand


@dataclass(frozen=True, slots=True)
class BillingRefundPreparation:
    command_id: UUID
    refund_id: UUID
    state: BillingCommandState
    command: BillingRefundCommand


class BillingProviderGateway(Protocol):
    async def create_checkout(self, *, command: BillingCheckoutCommand, idempotency_key: str) -> CheckoutSession: ...

    async def create_portal_session(self, *, command: BillingPortalCommand, idempotency_key: str) -> PortalSession: ...

    async def get_subscription(self, *, provider_subscription_reference: str) -> NormalizedSubscriptionSnapshot: ...

    async def list_events(
        self, *, cursor: str | None, occurred_from: datetime, occurred_to: datetime
    ) -> BillingEventPage: ...

    async def refund_first_payment(
        self, *, command: BillingRefundCommand, idempotency_key: str
    ) -> NormalizedBillingEvent: ...


class BillingWebhookVerifier(Protocol):
    def verify(self, *, raw_body: bytes, signature_header: str, received_at: datetime) -> NormalizedBillingEvent: ...


class BillingEventInbox(Protocol):
    async def admit(self, *, event: NormalizedBillingEvent, payload_digest: str) -> BillingWebhookAdmissionCode: ...


class SubscriptionRepository(Protocol):
    async def get_current(self, *, context: TenantContext) -> NormalizedSubscriptionSnapshot | None: ...


class BillingCommandRepository(Protocol):
    async def prepare_checkout(
        self,
        *,
        context: TenantContext,
        command_id: UUID,
        plan_version_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BillingCheckoutPreparation: ...

    async def prepare_portal(
        self,
        *,
        context: TenantContext,
        command_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BillingPortalPreparation: ...

    async def complete_checkout(
        self,
        *,
        context: TenantContext,
        preparation: BillingCheckoutPreparation,
        session: CheckoutSession,
    ) -> None: ...

    async def complete_portal(
        self,
        *,
        context: TenantContext,
        preparation: BillingPortalPreparation,
        session: PortalSession,
    ) -> None: ...

    async def mark_failed(self, *, context: TenantContext, command_id: UUID, reason: BillingErrorCode) -> None: ...

    async def mark_unknown(self, *, context: TenantContext, command_id: UUID) -> None: ...


class BillingRefundRepository(Protocol):
    async def prepare_refund(
        self,
        *,
        context: ActorContext,
        organization_id: UUID,
        subscription_id: UUID,
        command_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        now: datetime,
    ) -> BillingRefundPreparation: ...

    async def complete_refund(
        self, *, context: ActorContext, preparation: BillingRefundPreparation, provider_event_id: str
    ) -> None: ...

    async def mark_refund(self, *, context: ActorContext, command_id: UUID, unknown: bool) -> None: ...


class BillingReconciliationGateway(Protocol):
    async def classify_difference(
        self, *, local: NormalizedSubscriptionSnapshot, provider: NormalizedSubscriptionSnapshot
    ) -> BillingReconciliationDifferenceCode: ...
