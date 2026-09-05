from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.pipeline import GetPipelineBoardUseCase, ListPipelineColumnUseCase
from backend.app.domain.pipeline import PipelineStageView
from backend.app.domain.prospect import ProspectOrigin, ProspectStageCode, ProspectView
from backend.app.infrastructure.pagination import HmacCursorCodec

NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)
CURSOR_KEY = b"pipeline-board-pagination-test-key-32b"


class FixedClock:
    def now(self) -> datetime:
        return NOW


class Prospects:
    def __init__(self, items: tuple[ProspectView, ...]) -> None:
        self.items = items
        self.calls: list[dict[str, object]] = []

    async def list_active(self, **values: object) -> tuple[ProspectView, ...]:
        self.calls.append(values)
        rows = [item for item in self.items if item.stage_code.value == values["stage_code"]]
        after_id = values.get("after_id")
        if after_id is not None:
            rows = rows[next(index for index, item in enumerate(rows) if item.id == after_id) + 1 :]
        return tuple(rows[: int(values["limit"])])


class Pipeline:
    async def ensure_default_stages(self, **_: object) -> tuple[PipelineStageView, ...]:
        return (
            PipelineStageView(
                code=ProspectStageCode.NEW,
                position=1,
                color_token="slate",
                labels={"fr-CA": "Nouveau"},
                version=1,
            ),
        )


class UnitOfWork:
    def __init__(self, prospects: Prospects) -> None:
        self.prospects = prospects
        self.pipeline = Pipeline()

    async def __aenter__(self) -> UnitOfWork:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        del exc_type, exc_value, traceback

    async def commit(self) -> None:
        return None


def prospect(organization_id: UUID, index: int) -> ProspectView:
    created_at = NOW - timedelta(seconds=index)
    return ProspectView(
        id=uuid4(),
        organization_id=organization_id,
        internal_alias=f"Prospect {index}",
        origin=ProspectOrigin.MANUAL,
        source_label="Saisie manuelle",
        google_place_id=None,
        stage_code=ProspectStageCode.NEW,
        priority=0,
        version=1,
        created_at=created_at,
        updated_at=created_at,
        archived_at=None,
    )


@pytest.mark.asyncio
async def test_pipeline_loads_25_cards_then_a_signed_second_page() -> None:
    context = TenantContext(actor_id=uuid4(), organization_id=uuid4(), request_id="pipeline-pagination")
    prospects = Prospects(tuple(prospect(context.organization_id, index) for index in range(26)))
    unit_of_work = UnitOfWork(prospects)
    codec = HmacCursorCodec(CURSOR_KEY)
    board_use_case = GetPipelineBoardUseCase(lambda _: unit_of_work, FixedClock(), codec)  # type: ignore[arg-type]
    column_use_case = ListPipelineColumnUseCase(lambda _: unit_of_work, codec)  # type: ignore[arg-type]

    board = await board_use_case.execute(
        context=context, has_capability=True, search_text=None, owner_id=None, priority=None
    )

    assert len(board.columns["new"]) == 25
    assert board.next_cursors["new"] is not None
    assert prospects.calls[0]["limit"] == 26
    page = await column_use_case.execute(
        context=context,
        has_capability=True,
        stage_code="new",
        cursor=board.next_cursors["new"],
        limit=25,
        search_text=None,
        owner_id=None,
        priority=None,
    )
    assert [item.internal_alias for item in page.items] == ["Prospect 25"]
    assert page.next_cursor is None
