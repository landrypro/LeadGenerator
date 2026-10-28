"""Passerelle Stripe de sandbox : Checkout crée une session en attente."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

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
from ...domain.catalog import CurrencyCode
from .stripe_client import StripeSandboxClient
from .stripe_contract import subscription_snapshot_from_object


class StripeSandboxProviderGateway(BillingProviderGateway):
    def __init__(self, *, client: StripeSandboxClient, return_origin: str, portal_configuration_id: str = "") -> None:
        self._client = client
        self._return_origin = return_origin
        self._portal_configuration_id = portal_configuration_id

    async def create_checkout(self, *, command: BillingCheckoutCommand, idempotency_key: str) -> CheckoutSession:
        if command.amount_minor <= 0:
            raise BillingOperationError(BillingErrorCode.CATALOG_VERSION_UNAVAILABLE)
        command_reference = idempotency_key.removeprefix("checkout:")
        customer = command.provider_customer_reference
        if customer is None:
            customer = await self._client.create_customer(
                organization_reference=str(command.organization_id), idempotency_key=f"customer:{command_reference}"
            )
        checkout = await self._client.create_checkout(
            customer_reference=customer,
            price_reference=command.provider_price_reference,
            checkout_command_reference=command_reference,
            currency=command.currency,
            amount_minor=command.amount_minor,
            billing_cycle=command.billing_cycle,
            return_origin=self._return_origin,
            idempotency_key=idempotency_key,
        )
        return CheckoutSession(
            provider_checkout_reference=checkout.reference,
            provider_customer_reference=customer,
            provider_subscription_reference=None,
            subscription=None,
            checkout_url=checkout.url,
            expires_at=checkout.expires_at,
        )

    async def resume_checkout(
        self,
        *,
        reference: str,
        command_id: UUID,
        customer_reference: str,
        price_reference: str,
        currency: CurrencyCode,
    ) -> CheckoutSession:
        checkout = await self._client.resume_checkout(
            reference=reference,
            command_reference=str(command_id),
            customer_reference=customer_reference,
            price_reference=price_reference,
            currency=currency,
        )
        return CheckoutSession(
            provider_checkout_reference=checkout.reference,
            provider_customer_reference=customer_reference,
            provider_subscription_reference=None,
            subscription=None,
            checkout_url=checkout.url,
            expires_at=checkout.expires_at,
        )

    async def create_portal_session(self, *, command: BillingPortalCommand, idempotency_key: str) -> PortalSession:
        if not self._portal_configuration_id:
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        session = await self._client.create_portal_session(
            customer_reference=command.provider_customer_reference,
            configuration_reference=self._portal_configuration_id,
            return_origin=self._return_origin,
            idempotency_key=idempotency_key,
        )
        return PortalSession(
            provider_portal_reference=session.reference,
            portal_url=session.url,
            expires_at=None,
        )

    async def get_subscription(self, *, provider_subscription_reference: str) -> NormalizedSubscriptionSnapshot:
        return subscription_snapshot_from_object(
            await self._client.get_subscription(provider_subscription_reference), datetime.now(UTC)
        )

    async def list_events(
        self, *, cursor: str | None, occurred_from: datetime, occurred_to: datetime
    ) -> BillingEventPage:
        del cursor, occurred_from, occurred_to
        raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)

    async def refund_first_payment(
        self, *, command: BillingRefundCommand, idempotency_key: str
    ) -> NormalizedBillingEvent:
        del command, idempotency_key
        raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
