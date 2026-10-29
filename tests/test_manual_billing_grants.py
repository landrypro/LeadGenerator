from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from backend.app.application.errors import BillingOperationError, InsufficientCapability
from backend.app.application.ports.manual_billing_grants import (
    ManualBillingGrantMutationCode,
    ManualBillingGrantMutationResult,
    ManualBillingGrantView,
)
from backend.app.application.tenancy import ActorContext
from backend.app.application.use_cases.manual_billing_grants import (
    ManualBillingGrantUseCases,
    ProposeManualBillingGrantCommand,
)
from backend.app.domain.audit import AuditAction
from backend.app.domain.billing import BillingErrorCode, ManualBillingGrantReasonCode, ManualBillingGrantState

NOW = datetime(2026, 10, 30, 12, tzinfo=UTC)


@dataclass
class _Clock:
    def now(self) -> datetime:
        return NOW


@dataclass
class _Mutations:
    result: ManualBillingGrantMutationResult
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    async def list_options(self, **kwargs: object) -> tuple[()]:
        del kwargs
        return ()

    async def propose(self, **kwargs: object) -> ManualBillingGrantMutationResult:
        self.calls.append(("propose", kwargs))
        return self.result

    async def approve(self, **kwargs: object) -> ManualBillingGrantMutationResult:
        self.calls.append(("approve", kwargs))
        return self.result

    async def revoke(self, **kwargs: object) -> ManualBillingGrantMutationResult:
        self.calls.append(("revoke", kwargs))
        return self.result


@dataclass
class _Audit:
    events: list[object] = field(default_factory=list)

    async def record(self, event: object) -> UUID:
        self.events.append(event)
        return uuid4()


class _UnitOfWork:
    def __init__(self, result: ManualBillingGrantMutationResult) -> None:
        self.mutations = _Mutations(result)
        self.audit = _Audit()
        self.commits = 0

    async def __aenter__(self) -> _UnitOfWork:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def _grant(state: ManualBillingGrantState = ManualBillingGrantState.PENDING_APPROVAL) -> ManualBillingGrantView:
    return ManualBillingGrantView(
        id=uuid4(),
        organization_id=uuid4(),
        plan_version_id=uuid4(),
        plan_code="starter",
        version_number=4,
        currency="XAF",
        reason_code=ManualBillingGrantReasonCode.SANDBOX_VALIDATION,
        duration_days=31,
        state=state,
        starts_at=NOW if state is ManualBillingGrantState.ACTIVE else None,
        ends_at=NOW + timedelta(days=31) if state is ManualBillingGrantState.ACTIVE else None,
        version=1,
    )


def _service(
    result: ManualBillingGrantMutationResult, *, sandbox_enabled: bool = True
) -> tuple[ManualBillingGrantUseCases, _UnitOfWork, ActorContext]:
    unit = _UnitOfWork(result)
    service = ManualBillingGrantUseCases(lambda _: unit, _Clock(), sandbox_enabled=sandbox_enabled)
    return service, unit, ActorContext(uuid4(), "manual-grant-test")


def _proposal(grant: ManualBillingGrantView) -> ProposeManualBillingGrantCommand:
    return ProposeManualBillingGrantCommand(
        organization_id=grant.organization_id,
        plan_version_id=grant.plan_version_id,
        reason_code=grant.reason_code,
        duration_days=grant.duration_days,
    )


@pytest.mark.asyncio
async def test_manual_grant_proposal_is_idempotent_and_audited_once() -> None:
    grant = _grant()
    service, unit, context = _service(ManualBillingGrantMutationResult(ManualBillingGrantMutationCode.CREATED, grant))

    result = await service.propose(
        context=context,
        command=_proposal(grant),
        idempotency_key="manual-grant-proposal-key",
        has_platform_capability=True,
        session_issued_at=NOW,
    )

    assert result == grant
    assert unit.commits == 1
    assert len(unit.audit.events) == 1
    assert unit.audit.events[0].action is AuditAction.BILLING_MANUAL_GRANT_PROPOSED
    command, arguments = unit.mutations.calls[0]
    assert command == "propose"
    assert arguments["idempotency_key_digest"] != "manual-grant-proposal-key"
    assert len(str(arguments["idempotency_key_digest"])) == 64
    assert arguments["duration_days"] == 31

    replay_service, replay_unit, replay_context = _service(
        ManualBillingGrantMutationResult(ManualBillingGrantMutationCode.REPLAYED, grant)
    )
    replay = await replay_service.propose(
        context=replay_context,
        command=_proposal(grant),
        idempotency_key="manual-grant-proposal-key",
        has_platform_capability=True,
        session_issued_at=NOW,
    )
    assert replay == grant
    assert replay_unit.commits == 0
    assert replay_unit.audit.events == []


@pytest.mark.asyncio
async def test_manual_grant_requires_a_recent_platform_session_before_mutation() -> None:
    grant = _grant()
    service, unit, context = _service(ManualBillingGrantMutationResult(ManualBillingGrantMutationCode.CREATED, grant))

    with pytest.raises(InsufficientCapability):
        await service.propose(
            context=context,
            command=_proposal(grant),
            idempotency_key="manual-grant-stale-session",
            has_platform_capability=True,
            session_issued_at=NOW - timedelta(minutes=16),
        )

    assert unit.mutations.calls == []
    assert unit.audit.events == []


@pytest.mark.asyncio
async def test_manual_grant_approval_requires_a_distinct_approver() -> None:
    grant = _grant()
    service, unit, context = _service(
        ManualBillingGrantMutationResult(ManualBillingGrantMutationCode.APPROVAL_REQUIRED)
    )

    with pytest.raises(BillingOperationError) as raised:
        await service.approve(
            context=context,
            grant_id=grant.id,
            expected_version=grant.version,
            idempotency_key="manual-grant-self-approval",
            has_platform_capability=True,
            session_issued_at=NOW,
        )

    assert raised.value.code is BillingErrorCode.MANUAL_GRANT_APPROVAL_REQUIRED
    assert unit.commits == 0
    assert unit.audit.events == []


def test_manual_grant_duration_is_bounded_to_31_days() -> None:
    with pytest.raises(ValueError, match="1 et 31"):
        ProposeManualBillingGrantCommand(
            organization_id=uuid4(),
            plan_version_id=uuid4(),
            reason_code=ManualBillingGrantReasonCode.SANDBOX_SUPPORT,
            duration_days=32,
        )


@pytest.mark.asyncio
async def test_manual_grant_is_unavailable_outside_the_stripe_sandbox() -> None:
    grant = _grant()
    service, unit, context = _service(
        ManualBillingGrantMutationResult(ManualBillingGrantMutationCode.CREATED, grant), sandbox_enabled=False
    )

    with pytest.raises(BillingOperationError) as raised:
        await service.propose(
            context=context,
            command=_proposal(grant),
            idempotency_key="manual-grant-disabled",
            has_platform_capability=True,
            session_issued_at=NOW,
        )

    assert raised.value.code is BillingErrorCode.PROVIDER_DISABLED
    assert unit.mutations.calls == []
