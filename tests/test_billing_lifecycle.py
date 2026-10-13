from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from backend.app.application.errors import BillingOperationError
from backend.app.application.ports.billing import (
    BillingCommandState,
    BillingRefundCommand,
    BillingRefundPreparation,
)
from backend.app.application.tenancy import ActorContext
from backend.app.application.use_cases.billing_refunds import BillingRefundUseCases
from backend.app.domain.billing import (
    BillingErrorCode,
    SubscriptionState,
    SubscriptionTransitionTrigger,
    next_subscription_state,
)
from backend.app.infrastructure.billing.simulated import SimulatedBillingProviderGateway, SimulatedWebhookScenario

NOW = datetime(2026, 10, 10, 18, tzinfo=UTC)
SECRET = b"p53-07-simulator-secret-at-least-32-bytes"


@dataclass
class _Clock:
    now_value: datetime = NOW

    def now(self) -> datetime:
        return self.now_value


class _RefundRepository:
    def __init__(self, organization_id: UUID, subscription_id: UUID) -> None:
        self.organization_id = organization_id
        self.subscription_id = subscription_id
        self.command_id = uuid4()
        self.refund_id = uuid4()
        self.completed_event_id: str | None = None
        self.marked_unknown = False

    async def prepare_refund(self, **_: object) -> BillingRefundPreparation:
        return BillingRefundPreparation(
            self.command_id,
            self.refund_id,
            BillingCommandState.RESERVED,
            BillingRefundCommand(self.organization_id, "sim_first_paid_event"),
        )

    async def complete_refund(self, *, provider_event_id: str, **_: object) -> None:
        self.completed_event_id = provider_event_id

    async def mark_refund(self, *, unknown: bool, **_: object) -> None:
        self.marked_unknown = unknown


@pytest.mark.asyncio
async def test_simulated_refund_is_idempotent_and_exposes_no_provider_reference() -> None:
    organization_id, subscription_id = uuid4(), uuid4()
    repository = _RefundRepository(organization_id, subscription_id)
    provider = SimulatedBillingProviderGateway(webhook_secret=SECRET, clock=lambda: NOW)
    service = BillingRefundUseCases(repository, provider, _Clock())  # type: ignore[arg-type]
    arguments = {
        "context": ActorContext(uuid4(), "p53-07-refund"),
        "organization_id": organization_id,
        "subscription_id": subscription_id,
        "idempotency_key": "refund-key",
        "approved": True,
        "session_issued_at": NOW,
        "authorized": True,
    }

    first = await service.request_refund(**arguments)
    second = await service.request_refund(**arguments)

    assert first == second
    assert first.refund_id == repository.refund_id
    assert first.state == "approved"
    assert repository.completed_event_id is not None
    assert "sim_first_paid_event" not in repr(first)


@pytest.mark.asyncio
async def test_refund_timeout_after_effect_requires_reconciliation_without_blind_retry() -> None:
    organization_id, subscription_id = uuid4(), uuid4()
    repository = _RefundRepository(organization_id, subscription_id)
    provider = SimulatedBillingProviderGateway(webhook_secret=SECRET, clock=lambda: NOW)
    provider.configure_next_scenario(SimulatedWebhookScenario.PROVIDER_TIMEOUT_AFTER_EFFECT)
    service = BillingRefundUseCases(repository, provider, _Clock())  # type: ignore[arg-type]

    with pytest.raises(BillingOperationError) as raised:
        await service.request_refund(
            context=ActorContext(uuid4(), "p53-07-timeout"),
            organization_id=organization_id,
            subscription_id=subscription_id,
            idempotency_key="refund-timeout",
            approved=True,
            session_issued_at=NOW,
            authorized=True,
        )

    assert raised.value.code is BillingErrorCode.RECONCILIATION_REQUIRED
    assert repository.marked_unknown is True


def test_grace_and_cancellation_transitions_remain_closed() -> None:
    assert (
        next_subscription_state(SubscriptionState.PAST_DUE, SubscriptionTransitionTrigger.GRACE_PERIOD_STARTED)
        is SubscriptionState.GRACE_PERIOD
    )
    assert (
        next_subscription_state(SubscriptionState.GRACE_PERIOD, SubscriptionTransitionTrigger.GRACE_PERIOD_EXPIRED)
        is SubscriptionState.SUSPENDED
    )
    assert (
        next_subscription_state(SubscriptionState.ACTIVE, SubscriptionTransitionTrigger.CANCELLATION_SCHEDULED)
        is SubscriptionState.CANCELING
    )
    assert (
        next_subscription_state(SubscriptionState.CANCELING, SubscriptionTransitionTrigger.CANCELLATION_REVOKED)
        is SubscriptionState.ACTIVE
    )
    assert (
        next_subscription_state(SubscriptionState.CANCELING, SubscriptionTransitionTrigger.CANCELLATION_CONFIRMED)
        is SubscriptionState.CANCELED
    )


def test_refund_requires_explicit_approval_and_recent_platform_session() -> None:
    organization_id, subscription_id = uuid4(), uuid4()
    repository = _RefundRepository(organization_id, subscription_id)
    service = BillingRefundUseCases(
        repository, SimulatedBillingProviderGateway(webhook_secret=SECRET, clock=lambda: NOW), _Clock()
    )

    async def run() -> None:
        await service.request_refund(
            context=ActorContext(uuid4(), "p53-07-forbidden"),
            organization_id=organization_id,
            subscription_id=subscription_id,
            idempotency_key="refund-denied",
            approved=False,
            session_issued_at=NOW - timedelta(minutes=16),
            authorized=False,
        )

    with pytest.raises(BillingOperationError) as raised:
        import asyncio

        asyncio.run(run())
    assert raised.value.code is BillingErrorCode.CAPABILITY_REQUIRED
