from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from backend.app.application.errors import (
    InsufficientCapability,
    InvalidGoogleProspectCommand,
    InvalidGoogleSelectionGrant,
)
from backend.app.application.models import GoogleAccessOwner
from backend.app.application.ports import CursorCodec
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.prospects import (
    AddGoogleProspectsUseCase,
    CreateManualProspectUseCase,
    GoogleProspectInput,
    ListProspectsUseCase,
)
from backend.app.domain.prospect import ProspectDraft, ProspectOrigin, ProspectView


class FixedClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.value


class MemorySelectionGrants:
    def __init__(self, allowed: tuple[str, ...]) -> None:
        self.allowed = allowed

    async def issue(self, place_ids: tuple[str, ...], owner: GoogleAccessOwner, *, now: datetime) -> str:
        return "token"

    async def resolve(self, token: str, owner: GoogleAccessOwner, *, now: datetime) -> tuple[str, ...]:
        if token != "valid-token":
            raise InvalidGoogleSelectionGrant
        return self.allowed


class MemoryProspectRepository:
    def __init__(self) -> None:
        self.items: list[ProspectView] = []

    async def add(self, draft: ProspectDraft, *, now: datetime) -> ProspectView:
        view = ProspectView(
            id=uuid4(),
            organization_id=draft.organization_id,
            internal_alias=draft.internal_alias,
            origin=draft.origin,
            source_label=draft.source_label,
            google_place_id=draft.google_place_id,
            stage_code=draft.stage_code,
            priority=draft.priority,
            version=1,
            created_at=now,
            updated_at=now,
            archived_at=None,
        )
        self.items.append(view)
        return view

    async def get(self, prospect_id: UUID) -> ProspectView | None:
        return next((item for item in self.items if item.id == prospect_id), None)

    async def get_by_google_place_id(self, google_place_id: str) -> ProspectView | None:
        return next((item for item in self.items if item.google_place_id == google_place_id), None)

    async def list_active(
        self,
        *,
        limit: int,
        after_created_at: datetime | None = None,
        after_id: UUID | None = None,
        offset: int = 0,
    ) -> tuple[ProspectView, ...]:
        del after_created_at, after_id
        return tuple(self.items[offset : offset + limit])

    async def archive(self, prospect_id: UUID, *, expected_version: int, now: datetime) -> ProspectView | None:
        return None


class MemoryAuditRecorder:
    def __init__(self) -> None:
        self.events = []

    async def record(self, event: object) -> UUID:
        self.events.append(event)
        return uuid4()


@dataclass(slots=True)
class MemoryProspectUnitOfWork:
    prospects: MemoryProspectRepository
    audit: MemoryAuditRecorder
    committed: bool = False
    rolled_back: bool = False

    @property
    def contacts(self) -> object:
        raise NotImplementedError

    @property
    def contact_channels(self) -> object:
        raise NotImplementedError

    @property
    def provenance(self) -> object:
        raise NotImplementedError

    async def __aenter__(self) -> MemoryProspectUnitOfWork:
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

    async def rollback(self) -> None:
        self.rolled_back = True


class StaticCursorCodec(CursorCodec):
    def encode(self, created_at: datetime, item_id: UUID) -> str:
        return f"cursor:{item_id}"

    def decode(self, cursor: str | None) -> tuple[datetime | None, UUID | None]:
        return None, None


@pytest.fixture
def context() -> TenantContext:
    return TenantContext(actor_id=uuid4(), organization_id=uuid4(), request_id="prospect-use-case")


@pytest.mark.asyncio
async def test_create_manual_prospect_records_minimal_audit(context: TenantContext) -> None:
    repository = MemoryProspectRepository()
    audit = MemoryAuditRecorder()
    unit_of_work = MemoryProspectUnitOfWork(repository, audit)
    use_case = CreateManualProspectUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    prospect = await use_case.execute(context=context, internal_alias="Entreprise locale", has_capability=True)

    assert prospect.origin is ProspectOrigin.MANUAL
    assert prospect.google_place_id is None
    assert unit_of_work.committed is True
    assert len(audit.events) == 1


@pytest.mark.asyncio
async def test_add_google_prospects_uses_grant_and_does_not_duplicate(context: TenantContext) -> None:
    repository = MemoryProspectRepository()
    audit = MemoryAuditRecorder()
    unit_of_work = MemoryProspectUnitOfWork(repository, audit)
    use_case = AddGoogleProspectsUseCase(
        lambda _: unit_of_work,  # type: ignore[arg-type]
        MemorySelectionGrants(("place-1", "place-2")),
        FixedClock(),
    )
    owner = GoogleAccessOwner(user_id=context.actor_id, organization_id=context.organization_id)

    first = await use_case.execute(
        context=context,
        owner=owner,
        selection_token="valid-token",
        items=(GoogleProspectInput(place_id="place-1", internal_alias="Plomberie Nord"),),
        has_capability=True,
    )
    second = await use_case.execute(
        context=context,
        owner=owner,
        selection_token="valid-token",
        items=(GoogleProspectInput(place_id="place-1", internal_alias="Alias ignoré au rejeu"),),
        has_capability=True,
    )

    assert first.items[0].disposition == "created"
    assert first.items[0].prospect.internal_alias == "Plomberie Nord"
    assert first.items[0].prospect.google_place_id == "place-1"
    assert second.items[0].prospect.internal_alias == "Plomberie Nord"
    assert second.items[0].disposition == "existing"
    assert len(repository.items) == 1
    assert len(audit.events) == 1


@pytest.mark.asyncio
async def test_add_google_prospects_rejects_place_outside_grant(context: TenantContext) -> None:
    use_case = AddGoogleProspectsUseCase(
        lambda _: MemoryProspectUnitOfWork(MemoryProspectRepository(), MemoryAuditRecorder()),  # type: ignore[arg-type]
        MemorySelectionGrants(("place-1",)),
        FixedClock(),
    )

    with pytest.raises(InvalidGoogleSelectionGrant):
        await use_case.execute(
            context=context,
            owner=GoogleAccessOwner(user_id=context.actor_id, organization_id=context.organization_id),
            selection_token="valid-token",
            items=(GoogleProspectInput(place_id="place-2", internal_alias="Entreprise hors sélection"),),
            has_capability=True,
        )


@pytest.mark.asyncio
async def test_add_google_prospects_rejects_duplicate_place_ids(context: TenantContext) -> None:
    use_case = AddGoogleProspectsUseCase(
        lambda _: MemoryProspectUnitOfWork(MemoryProspectRepository(), MemoryAuditRecorder()),  # type: ignore[arg-type]
        MemorySelectionGrants(("place-1",)),
        FixedClock(),
    )

    with pytest.raises(InvalidGoogleProspectCommand):
        await use_case.execute(
            context=context,
            owner=GoogleAccessOwner(user_id=context.actor_id, organization_id=context.organization_id),
            selection_token="valid-token",
            items=(
                GoogleProspectInput(place_id="place-1", internal_alias="Premier nom"),
                GoogleProspectInput(place_id="place-1", internal_alias="Second nom"),
            ),
            has_capability=True,
        )


@pytest.mark.asyncio
async def test_prospect_capability_is_required(context: TenantContext) -> None:
    use_case = ListProspectsUseCase(
        lambda _: MemoryProspectUnitOfWork(MemoryProspectRepository(), MemoryAuditRecorder()),  # type: ignore[arg-type]
        StaticCursorCodec(),
    )

    with pytest.raises(InsufficientCapability):
        await use_case.execute(context=context, has_capability=False, cursor=None, limit=25)
