from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from backend.app.application.errors import BillingOperationError
from backend.app.application.ports.billing import (
    BillingCheckoutCommand,
    BillingCheckoutPreparation,
    BillingCommandState,
    BillingPortalCommand,
    BillingPortalPreparation,
    BillingReturnTarget,
    CheckoutSession,
    PortalSession,
)
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.billing import BillingSessionUseCases
from backend.app.domain.billing import BillingErrorCode
from backend.app.domain.catalog import CurrencyCode
from backend.app.infrastructure.billing.simulated import (
    SimulatedBillingProviderGateway,
    SimulatedWebhookScenario,
)

NOW = datetime(2026, 10, 10, 14, tzinfo=UTC)
SECRET = b"p53-06-simulator-secret-at-least-32-bytes"


@dataclass
class _Clock:
    def now(self) -> datetime:
        return NOW


class _Repository:
    def __init__(self, organization_id: UUID, plan_version_id: UUID) -> None:
        self.command_id = uuid4()
        self.state = BillingCommandState.RESERVED
        self.checkout_command = BillingCheckoutCommand(
            organization_id,
            plan_version_id,
            CurrencyCode.CAD,
            f"sim_price_{str(plan_version_id).replace('-', '')}",
            BillingReturnTarget.SUBSCRIPTION,
        )
        self.portal_command = BillingPortalCommand(
            organization_id, "sim_customer_server_selected", BillingReturnTarget.SUBSCRIPTION
        )
        self.completed_checkout: CheckoutSession | None = None
        self.completed_portal: PortalSession | None = None
        self.failure_marks: list[BillingCommandState] = []

    async def prepare_checkout(self, **_: object) -> BillingCheckoutPreparation:
        return BillingCheckoutPreparation(self.command_id, self.state, self.checkout_command)

    async def prepare_portal(self, **_: object) -> BillingPortalPreparation:
        return BillingPortalPreparation(self.command_id, self.state, self.portal_command)

    async def complete_checkout(self, *, session: CheckoutSession, **_: object) -> None:
        self.completed_checkout = session
        self.state = BillingCommandState.SUCCEEDED

    async def complete_portal(self, *, session: PortalSession, **_: object) -> None:
        self.completed_portal = session
        self.state = BillingCommandState.SUCCEEDED

    async def mark_failed(self, **_: object) -> None:
        self.failure_marks.append(BillingCommandState.FAILED)
        self.state = BillingCommandState.FAILED

    async def mark_unknown(self, **_: object) -> None:
        self.failure_marks.append(BillingCommandState.UNKNOWN)
        self.state = BillingCommandState.UNKNOWN


def _service() -> tuple[BillingSessionUseCases, _Repository, SimulatedBillingProviderGateway, TenantContext]:
    organization_id = uuid4()
    repository = _Repository(organization_id, uuid4())
    provider = SimulatedBillingProviderGateway(webhook_secret=SECRET, clock=lambda: NOW)
    return (
        BillingSessionUseCases(repository, provider, _Clock()),  # type: ignore[arg-type]
        repository,
        provider,
        TenantContext(uuid4(), organization_id, "request-p53-06"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("currency", list(CurrencyCode))
async def test_checkout_uses_only_server_selected_price_and_returns_minimized_grant(currency: CurrencyCode) -> None:
    service, repository, _, context = _service()
    command = repository.checkout_command
    repository.checkout_command = BillingCheckoutCommand(
        command.organization_id,
        command.plan_version_id,
        currency,
        command.provider_price_reference,
        command.return_target,
    )

    grant = await service.create_checkout(
        context=context,
        plan_version_id=repository.checkout_command.plan_version_id,
        idempotency_key="checkout-safe-key",
        return_target=BillingReturnTarget.SUBSCRIPTION,
        authorized=True,
        session_issued_at=NOW - timedelta(minutes=2),
    )

    assert grant.url.startswith("http://billing-simulator.local/checkout/")
    assert grant.expires_at == NOW + timedelta(minutes=30)
    assert repository.completed_checkout is not None
    assert repository.completed_checkout.subscription.currency is currency
    assert (
        repository.completed_checkout.subscription.provider_price_reference
        == repository.checkout_command.provider_price_reference
    )


@pytest.mark.asyncio
async def test_checkout_replay_returns_the_same_provider_session() -> None:
    service, repository, _, context = _service()
    arguments = {
        "context": context,
        "plan_version_id": repository.checkout_command.plan_version_id,
        "idempotency_key": "same-checkout-key",
        "return_target": BillingReturnTarget.SUBSCRIPTION,
        "authorized": True,
        "session_issued_at": NOW,
    }

    first = await service.create_checkout(**arguments)
    second = await service.create_checkout(**arguments)

    assert second == first


@pytest.mark.asyncio
async def test_stale_session_is_rejected_before_any_durable_command() -> None:
    service, repository, _, context = _service()

    with pytest.raises(BillingOperationError) as raised:
        await service.create_portal(
            context=context,
            idempotency_key="portal-key",
            return_target=BillingReturnTarget.SUBSCRIPTION,
            authorized=True,
            session_issued_at=NOW - timedelta(minutes=16),
        )

    assert raised.value.code is BillingErrorCode.CAPABILITY_REQUIRED
    assert repository.completed_portal is None


@pytest.mark.asyncio
async def test_timeout_after_possible_effect_marks_unknown_and_blocks_blind_retry() -> None:
    service, repository, provider, context = _service()
    provider.configure_next_scenario(SimulatedWebhookScenario.PROVIDER_TIMEOUT_AFTER_EFFECT)
    arguments = {
        "context": context,
        "plan_version_id": repository.checkout_command.plan_version_id,
        "idempotency_key": "ambiguous-checkout-key",
        "return_target": BillingReturnTarget.SUBSCRIPTION,
        "authorized": True,
        "session_issued_at": NOW,
    }

    with pytest.raises(BillingOperationError) as first:
        await service.create_checkout(**arguments)
    with pytest.raises(BillingOperationError) as replay:
        await service.create_checkout(**arguments)

    assert first.value.code is BillingErrorCode.RECONCILIATION_REQUIRED
    assert replay.value.code is BillingErrorCode.RECONCILIATION_REQUIRED
    assert repository.failure_marks == [BillingCommandState.UNKNOWN]
