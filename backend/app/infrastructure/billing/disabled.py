"""Adaptateur d'arrêt d'urgence Billing, actif par défaut."""

from __future__ import annotations

from datetime import datetime
from typing import NoReturn

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
from ...domain.billing import BillingErrorCode


class DisabledBillingProviderGateway(BillingProviderGateway):
    """Refuse toute commande et toute lecture fournisseur sans effet externe."""

    @staticmethod
    def _disabled() -> NoReturn:
        raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)

    async def create_checkout(self, *, command: BillingCheckoutCommand, idempotency_key: str) -> CheckoutSession:
        del command, idempotency_key
        self._disabled()

    async def create_portal_session(self, *, command: BillingPortalCommand, idempotency_key: str) -> PortalSession:
        del command, idempotency_key
        self._disabled()

    async def get_subscription(self, *, provider_subscription_reference: str) -> NormalizedSubscriptionSnapshot:
        del provider_subscription_reference
        self._disabled()

    async def list_events(
        self, *, cursor: str | None, occurred_from: datetime, occurred_to: datetime
    ) -> BillingEventPage:
        del cursor, occurred_from, occurred_to
        self._disabled()

    async def refund_first_payment(
        self, *, command: BillingRefundCommand, idempotency_key: str
    ) -> NormalizedBillingEvent:
        del command, idempotency_key
        self._disabled()
