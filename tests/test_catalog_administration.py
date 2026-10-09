from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.application.errors import CatalogApprovalRequired, CatalogConcurrentUpdate, InsufficientCapability
from backend.app.application.ports.catalog import (
    CatalogMutationResult,
    CatalogMutationResultCode,
    CatalogPlanView,
    PlanContractOverrideView,
)
from backend.app.application.tenancy import ActorContext
from backend.app.application.use_cases.catalog import (
    CatalogAdministrationUseCases,
    CreateCatalogPlanCommand,
    CreateCatalogPlanVersionCommand,
    ProposePlanContractOverrideCommand,
)
from backend.app.domain.audit import AuditAction, AuditMetadataPolicy, InvalidAuditMetadata
from backend.app.domain.catalog import (
    ENTITLEMENT_REGISTRY,
    CatalogValidationError,
    ContractState,
    CurrencyCode,
    EntitlementKey,
    EntitlementKind,
    EntitlementValue,
    OverrideState,
    PlanCode,
)

NOW = datetime(2026, 10, 7, 14, tzinfo=UTC)
ACTOR = uuid4()
CONTEXT = ActorContext(ACTOR, "p52-03-unit")


class FrozenClock:
    def now(self) -> datetime:
        return NOW


class FakeAudit:
    def __init__(self) -> None:
        self.events = []

    async def record(self, event):
        self.events.append(event)
        return event.id


class FakeMutations:
    def __init__(self, *results: CatalogMutationResult) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def _next(self, name: str, **kwargs: object) -> CatalogMutationResult:
        self.calls.append((name, kwargs))
        return self.results.pop(0)

    async def create_plan(self, **kwargs: object) -> CatalogMutationResult:
        return await self._next("create_plan", **kwargs)

    async def create_plan_version(self, **kwargs: object) -> CatalogMutationResult:
        return await self._next("create_plan_version", **kwargs)

    async def publish_plan_version(self, **kwargs: object) -> CatalogMutationResult:
        return await self._next("publish_plan_version", **kwargs)

    async def attach_organization_contract(self, **kwargs: object) -> CatalogMutationResult:
        return await self._next("attach_organization_contract", **kwargs)

    async def change_contract_state(self, **kwargs: object) -> CatalogMutationResult:
        return await self._next("change_contract_state", **kwargs)

    async def propose_contract_override(self, **kwargs: object) -> CatalogMutationResult:
        return await self._next("propose_contract_override", **kwargs)

    async def approve_contract_override(self, **kwargs: object) -> CatalogMutationResult:
        return await self._next("approve_contract_override", **kwargs)

    async def revoke_contract_override(self, **kwargs: object) -> CatalogMutationResult:
        return await self._next("revoke_contract_override", **kwargs)


class FakeUnitOfWork:
    def __init__(self, mutations: FakeMutations) -> None:
        self.mutations = mutations
        self.audit = FakeAudit()
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _rights() -> tuple[EntitlementValue, ...]:
    values = []
    for key, definition in ENTITLEMENT_REGISTRY.items():
        values.append(
            EntitlementValue(key, definition.kind, integer_value=1)
            if definition.kind is EntitlementKind.LIMIT
            else EntitlementValue(key, definition.kind, boolean_value=False)
        )
    return tuple(values)


def test_create_plan_requires_platform_capability_and_records_safe_audit() -> None:
    plan = CatalogPlanView(uuid4(), PlanCode.FREEMIUM, "draft", 0, 1)
    uow = FakeUnitOfWork(FakeMutations(CatalogMutationResult(CatalogMutationResultCode.CREATED, plan=plan)))
    use_cases = CatalogAdministrationUseCases(lambda _: uow, FrozenClock())

    with pytest.raises(InsufficientCapability):
        import asyncio

        asyncio.run(
            use_cases.create_plan(
                context=CONTEXT, command=CreateCatalogPlanCommand(PlanCode.FREEMIUM, 0), has_platform_capability=False
            )
        )

    import asyncio

    result = asyncio.run(
        use_cases.create_plan(
            context=CONTEXT, command=CreateCatalogPlanCommand(PlanCode.FREEMIUM, 0), has_platform_capability=True
        )
    )

    assert result == plan
    assert uow.committed is True
    assert uow.audit.events[0].action is AuditAction.CATALOG_PLAN_CREATED
    assert uow.audit.events[0].metadata == {"plan_code": "freemium", "display_order": 0}


def test_version_requires_full_registry_and_separate_approval_result_is_explicit() -> None:
    with pytest.raises(CatalogValidationError):
        CreateCatalogPlanVersionCommand(uuid4(), 1, CurrencyCode.CAD, "monthly", 0, NOW, None, _rights()[:-1])

    uow = FakeUnitOfWork(FakeMutations(CatalogMutationResult(CatalogMutationResultCode.APPROVAL_REQUIRED)))
    use_cases = CatalogAdministrationUseCases(lambda _: uow, FrozenClock())
    import asyncio

    with pytest.raises(CatalogApprovalRequired):
        asyncio.run(
            use_cases.publish_plan_version(
                context=CONTEXT, version_id=uuid4(), expected_version=1, has_platform_capability=True
            )
        )
    assert uow.committed is False


def test_contract_state_change_exposes_optimistic_concurrency() -> None:
    uow = FakeUnitOfWork(
        FakeMutations(CatalogMutationResult(CatalogMutationResultCode.VERSION_CONFLICT, current_version=3))
    )
    use_cases = CatalogAdministrationUseCases(lambda _: uow, FrozenClock())
    import asyncio

    with pytest.raises(CatalogConcurrentUpdate) as error:
        asyncio.run(
            use_cases.change_contract_state(
                context=CONTEXT,
                contract_id=uuid4(),
                expected_version=1,
                state=ContractState.SUSPENDED,
                has_platform_capability=True,
            )
        )
    assert error.value.current_version == 3


def test_catalog_audit_metadata_is_closed_and_non_sensitive() -> None:
    plan_id = uuid4()
    assert AuditMetadataPolicy.validate(
        AuditAction.CATALOG_PLAN_VERSION_CREATED, {"plan_id": plan_id, "version_number": 2}
    ) == {"plan_id": str(plan_id), "version_number": 2}
    with pytest.raises(InvalidAuditMetadata):
        AuditMetadataPolicy.validate(
            AuditAction.CATALOG_CONTRACT_ATTACHED,
            {"organization_id": uuid4(), "plan_version_id": uuid4(), "state": "active", "price": 1},
        )


def test_catalog_replay_reuses_the_same_resource_identity_without_a_second_audit() -> None:
    import asyncio

    operation_id = uuid4()
    plan = CatalogPlanView(uuid4(), PlanCode.BUSINESS, "draft", 2, 1)
    mutations = FakeMutations(
        CatalogMutationResult(CatalogMutationResultCode.CREATED, plan=plan),
        CatalogMutationResult(CatalogMutationResultCode.REPLAYED, plan=plan),
    )
    uow = FakeUnitOfWork(mutations)
    use_cases = CatalogAdministrationUseCases(lambda _: uow, FrozenClock())
    command = CreateCatalogPlanCommand(PlanCode.BUSINESS, 2, operation_id=operation_id)

    assert asyncio.run(use_cases.create_plan(context=CONTEXT, command=command, has_platform_capability=True)) == plan
    assert asyncio.run(use_cases.create_plan(context=CONTEXT, command=command, has_platform_capability=True)) == plan
    assert mutations.calls[0][1]["plan_id"] == mutations.calls[1][1]["plan_id"]
    assert len(uow.audit.events) == 1


def test_contract_override_transitions_are_audited_without_the_value_or_justification() -> None:
    import asyncio

    organization_id, contract_id, override_id, approver = uuid4(), uuid4(), uuid4(), uuid4()
    proposed = PlanContractOverrideView(
        override_id,
        organization_id,
        contract_id,
        EntitlementKey.ACTIVE_MEMBERS_MAX,
        EntitlementKind.LIMIT,
        4,
        None,
        OverrideState.PENDING_APPROVAL,
        ACTOR,
        None,
        NOW,
        NOW.replace(day=8),
        1,
    )
    approved = PlanContractOverrideView(
        override_id,
        organization_id,
        contract_id,
        EntitlementKey.ACTIVE_MEMBERS_MAX,
        EntitlementKind.LIMIT,
        4,
        None,
        OverrideState.ACTIVE,
        ACTOR,
        approver,
        NOW,
        NOW.replace(day=8),
        2,
    )
    revoked = PlanContractOverrideView(
        override_id,
        organization_id,
        contract_id,
        EntitlementKey.ACTIVE_MEMBERS_MAX,
        EntitlementKind.LIMIT,
        4,
        None,
        OverrideState.REVOKED,
        ACTOR,
        approver,
        NOW,
        NOW.replace(day=8),
        3,
    )
    mutations = FakeMutations(
        CatalogMutationResult(CatalogMutationResultCode.CREATED, contract_override=proposed),
        CatalogMutationResult(CatalogMutationResultCode.UPDATED, contract_override=approved),
        CatalogMutationResult(CatalogMutationResultCode.UPDATED, contract_override=revoked),
    )
    uow = FakeUnitOfWork(mutations)
    use_cases = CatalogAdministrationUseCases(lambda _: uow, FrozenClock())
    command = ProposePlanContractOverrideCommand(
        contract_id,
        EntitlementValue(EntitlementKey.ACTIVE_MEMBERS_MAX, EntitlementKind.LIMIT, integer_value=4),
        "synthetic reason",
        NOW,
        NOW.replace(day=8),
    )

    assert (
        asyncio.run(use_cases.propose_contract_override(context=CONTEXT, command=command, has_platform_capability=True))
        == proposed
    )
    assert (
        asyncio.run(
            use_cases.approve_contract_override(
                context=ActorContext(approver, "p52-06-unit-approve"),
                override_id=override_id,
                expected_version=1,
                has_platform_capability=True,
            )
        )
        == approved
    )
    assert (
        asyncio.run(
            use_cases.revoke_contract_override(
                context=ActorContext(approver, "p52-06-unit-revoke"),
                override_id=override_id,
                expected_version=2,
                has_platform_capability=True,
            )
        )
        == revoked
    )
    assert [event.action for event in uow.audit.events] == [
        AuditAction.CATALOG_CONTRACT_OVERRIDE_PROPOSED,
        AuditAction.CATALOG_CONTRACT_OVERRIDE_APPROVED,
        AuditAction.CATALOG_CONTRACT_OVERRIDE_REVOKED,
    ]
    assert all(
        "justification" not in event.metadata and "integer_value" not in event.metadata for event in uow.audit.events
    )
