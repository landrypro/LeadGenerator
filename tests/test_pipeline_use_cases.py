from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.pipeline import MoveProspectStageUseCase
from backend.app.domain.pipeline import PipelineValidationError, ProspectStageTransitionView
from backend.app.domain.prospect import ProspectOrigin, ProspectStageCode, ProspectView


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


class MemoryProspects:
    def __init__(self, item: ProspectView) -> None:
        self.item = item

    async def get(self, prospect_id: UUID) -> ProspectView | None:
        return self.item if prospect_id == self.item.id else None

    async def change_stage(
        self, prospect_id: UUID, *, expected_version: int, from_stage: str, to_stage: str, now: datetime
    ) -> ProspectView | None:
        if (
            prospect_id != self.item.id
            or self.item.version != expected_version
            or self.item.stage_code.value != from_stage
        ):
            return None
        self.item = replace(
            self.item,
            stage_code=ProspectStageCode(to_stage),
            version=self.item.version + 1,
            updated_at=now,
            stage_changed_at=now,
        )
        return self.item


class MemoryPipeline:
    def __init__(self) -> None:
        self.items: dict[str, ProspectStageTransitionView] = {}

    async def get_transition_by_idempotency_key(
        self, *, prospect_id: UUID, idempotency_key: str
    ) -> ProspectStageTransitionView | None:
        return self.items.get(idempotency_key)

    async def add_transition(self, **values: object) -> ProspectStageTransitionView:
        view = ProspectStageTransitionView(
            id=uuid4(),
            prospect_id=values["prospect_id"],
            actor_id=values["actor_id"],
            from_stage=ProspectStageCode(values["from_stage"]),
            to_stage=ProspectStageCode(values["to_stage"]),
            from_version=values["from_version"],
            resulting_version=values["resulting_version"],
            reason_code=values["reason_code"],
            reason_note=values["reason_note"],
            occurred_at=values["now"],
        )
        self.items[values["idempotency_key"]] = view
        return view


class MemoryAudit:
    async def record(self, event: object) -> UUID:
        return uuid4()


class UnitOfWork:
    def __init__(self, prospect: ProspectView) -> None:
        self.prospects = MemoryProspects(prospect)
        self.pipeline = MemoryPipeline()
        self.audit = MemoryAudit()
        self.committed = False

    async def __aenter__(self) -> UnitOfWork:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        del exc_type, exc_value, traceback

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None


@pytest.fixture
def context() -> TenantContext:
    return TenantContext(actor_id=uuid4(), organization_id=uuid4(), request_id="pipeline-test")


@pytest.fixture
def prospect(context: TenantContext) -> ProspectView:
    now = FixedClock().now()
    return ProspectView(
        id=uuid4(),
        organization_id=context.organization_id,
        internal_alias="Atelier",
        origin=ProspectOrigin.MANUAL,
        source_label="Saisie manuelle",
        google_place_id=None,
        stage_code=ProspectStageCode.NEW,
        priority=0,
        version=1,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )


@pytest.mark.asyncio
async def test_move_pipeline_transition_is_versioned_and_idempotent(
    context: TenantContext, prospect: ProspectView
) -> None:
    unit_of_work = UnitOfWork(prospect)
    use_case = MoveProspectStageUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    updated, first = await use_case.execute(
        context=context,
        prospect_id=prospect.id,
        expected_version=1,
        to_stage="qualifying",
        reason_code=None,
        reason_note=None,
        idempotency_key="command-0001",
        has_capability=True,
    )
    replayed, second = await use_case.execute(
        context=context,
        prospect_id=prospect.id,
        expected_version=1,
        to_stage="qualifying",
        reason_code=None,
        reason_note=None,
        idempotency_key="command-0001",
        has_capability=True,
    )

    assert updated.stage_code is ProspectStageCode.QUALIFYING
    assert updated.version == 2
    assert first.id == second.id
    assert replayed.version == 2
    assert unit_of_work.committed is True


@pytest.mark.asyncio
async def test_lost_requires_controlled_reason(context: TenantContext, prospect: ProspectView) -> None:
    unit_of_work = UnitOfWork(prospect)
    use_case = MoveProspectStageUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    with pytest.raises(PipelineValidationError):
        await use_case.execute(
            context=context,
            prospect_id=prospect.id,
            expected_version=1,
            to_stage="lost",
            reason_code=None,
            reason_note=None,
            idempotency_key="command-0002",
            has_capability=True,
        )
