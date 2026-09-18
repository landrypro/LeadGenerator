from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from backend.app.application.errors import InsufficientCapability, OpportunityVersionConflict
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.opportunities import TransitionOpportunityUseCase, UpdateOpportunityUseCase
from backend.app.domain.opportunity import (
    OpportunityEventType,
    OpportunityEventView,
    OpportunityStageCode,
    OpportunityView,
)


class _FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 10, 12, tzinfo=UTC)


class _Opportunities:
    def __init__(self, item: OpportunityView) -> None:
        self.item = item

    async def get(self, opportunity_id: UUID) -> OpportunityView | None:
        return self.item if opportunity_id == self.item.id else None

    async def get_for_update(self, opportunity_id: UUID) -> OpportunityView | None:
        return await self.get(opportunity_id)

    async def update(
        self, opportunity_id: UUID, *, expected_version: int, changes: dict[str, object], now: datetime
    ) -> OpportunityView | None:
        if opportunity_id != self.item.id or expected_version != self.item.version:
            return None
        self.item = replace(self.item, **changes, version=self.item.version + 1, updated_at=now)
        return self.item


class _Events:
    def __init__(self) -> None:
        self.replays: dict[tuple[OpportunityEventType, str], OpportunityEventView] = {}

    async def get_by_idempotency_key(
        self, *, event_type: OpportunityEventType, idempotency_key: str
    ) -> OpportunityEventView | None:
        return self.replays.get((event_type, idempotency_key))

    async def add(self, event: OpportunityEventView) -> None:
        self.replays[(event.event_type, event.idempotency_key)] = event


class _Audit:
    def __init__(self) -> None:
        self.items: list[object] = []

    async def record(self, item: object) -> UUID:
        self.items.append(item)
        return uuid4()


@dataclass
class _UnitOfWork:
    opportunities: _Opportunities
    opportunity_events: _Events
    audit: _Audit
    committed: bool = False

    async def __aenter__(self) -> "_UnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback

    async def commit(self) -> None:
        self.committed = True


def _context() -> TenantContext:
    return TenantContext(actor_id=uuid4(), organization_id=uuid4(), request_id="opportunity-use-case")


def _opportunity(context: TenantContext, owner_id: UUID, *, version: int = 1) -> OpportunityView:
    now = datetime(2026, 9, 10, 11, tzinfo=UTC)
    return OpportunityView(
        id=uuid4(),
        organization_id=context.organization_id,
        prospect_id=uuid4(),
        owner_membership_id=owner_id,
        name="Préparation proposition",
        amount=Decimal("1000"),
        currency_code="CAD",
        probability=25,
        stage_code=OpportunityStageCode.DISCOVERY,
        expected_close_on=date(2026, 9, 1),
        loss_reason_code=None,
        loss_reason_note=None,
        closed_at=None,
        created_by=context.actor_id,
        version=version,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_update_preserves_an_old_deadline_when_another_field_changes() -> None:
    context = _context()
    owner_id = uuid4()
    unit_of_work = _UnitOfWork(_Opportunities(_opportunity(context, owner_id)), _Events(), _Audit())
    use_case = UpdateOpportunityUseCase(lambda _context: unit_of_work, _FixedClock())  # type: ignore[arg-type]

    updated = await use_case.execute(
        context=context,
        opportunity_id=unit_of_work.opportunities.item.id,
        expected_version=1,
        changes={"name": "Proposition révisée"},
        idempotency_key="opportunity-update-1",
        can_update=True,
        can_manage=False,
        current_membership_id=owner_id,
    )

    assert updated.name == "Proposition révisée"
    assert updated.expected_close_on == date(2026, 9, 1)
    assert updated.version == 2
    assert unit_of_work.committed is True
    assert len(unit_of_work.audit.items) == 1


@pytest.mark.asyncio
async def test_update_rejects_a_stale_version_before_writing() -> None:
    context = _context()
    owner_id = uuid4()
    unit_of_work = _UnitOfWork(_Opportunities(_opportunity(context, owner_id, version=2)), _Events(), _Audit())
    use_case = UpdateOpportunityUseCase(lambda _context: unit_of_work, _FixedClock())  # type: ignore[arg-type]

    with pytest.raises(OpportunityVersionConflict) as error:
        await use_case.execute(
            context=context,
            opportunity_id=unit_of_work.opportunities.item.id,
            expected_version=1,
            changes={"name": "Proposition révisée"},
            idempotency_key="opportunity-update-stale",
            can_update=True,
            can_manage=False,
            current_membership_id=owner_id,
        )

    assert error.value.current_version == 2
    assert unit_of_work.committed is False


@pytest.mark.asyncio
async def test_update_rejects_reassignment_by_a_sales_member() -> None:
    context = _context()
    owner_id = uuid4()
    unit_of_work = _UnitOfWork(_Opportunities(_opportunity(context, owner_id)), _Events(), _Audit())
    use_case = UpdateOpportunityUseCase(lambda _context: unit_of_work, _FixedClock())  # type: ignore[arg-type]

    with pytest.raises(InsufficientCapability):
        await use_case.execute(
            context=context,
            opportunity_id=unit_of_work.opportunities.item.id,
            expected_version=1,
            changes={"owner_membership_id": uuid4()},
            idempotency_key="opportunity-reassign-forbidden",
            can_update=True,
            can_manage=False,
            current_membership_id=owner_id,
        )

    assert unit_of_work.committed is False


@pytest.mark.asyncio
async def test_transition_to_won_records_closed_at_in_audit_and_commits() -> None:
    context = _context()
    owner_id = uuid4()
    proposal = replace(
        _opportunity(context, owner_id, version=3),
        stage_code=OpportunityStageCode.PROPOSAL,
        probability=60,
    )
    unit_of_work = _UnitOfWork(_Opportunities(proposal), _Events(), _Audit())
    use_case = TransitionOpportunityUseCase(lambda _context: unit_of_work, _FixedClock())  # type: ignore[arg-type]

    won = await use_case.execute(
        context=context,
        opportunity_id=proposal.id,
        expected_version=proposal.version,
        to_stage=OpportunityStageCode.WON,
        reason_code=None,
        reason_note=None,
        idempotency_key="opportunity-win-1",
        can_close=True,
        can_manage=False,
        current_membership_id=owner_id,
    )

    assert won.stage_code is OpportunityStageCode.WON
    assert won.probability == 100
    assert won.closed_at == _FixedClock().now()
    assert won.version == 4
    assert unit_of_work.committed is True
    assert len(unit_of_work.audit.items) == 1
    assert unit_of_work.audit.items[0].metadata["changed_fields"] == (
        "closed_at",
        "probability",
        "stage_code",
    )
