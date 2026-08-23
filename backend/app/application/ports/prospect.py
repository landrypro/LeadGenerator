from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from ...domain.prospect import (
    ContactChannelDraft,
    ContactChannelView,
    ContactDraft,
    ContactView,
    ProspectDraft,
    ProspectView,
    ProvenanceDraft,
    ProvenanceView,
)
from ..models import GoogleAccessOwner
from ..tenancy import TenantContext
from .audit import AuditRecorder


class ProspectRepository(Protocol):
    async def add(self, draft: ProspectDraft, *, now: datetime) -> ProspectView: ...

    async def get(self, prospect_id: UUID) -> ProspectView | None: ...

    async def get_by_google_place_id(self, google_place_id: str) -> ProspectView | None: ...

    async def list_active(
        self,
        *,
        limit: int,
        after_created_at: datetime | None = None,
        after_id: UUID | None = None,
        offset: int = 0,
    ) -> tuple[ProspectView, ...]: ...

    async def archive(self, prospect_id: UUID, *, expected_version: int, now: datetime) -> ProspectView | None: ...


class ContactRepository(Protocol):
    async def add(self, draft: ContactDraft, *, now: datetime) -> ContactView: ...

    async def get(self, contact_id: UUID) -> ContactView | None: ...


class ContactChannelRepository(Protocol):
    async def add(self, draft: ContactChannelDraft, *, now: datetime) -> ContactChannelView: ...

    async def find_by_normalized_value(
        self,
        *,
        channel_type: str,
        value_normalized: str,
    ) -> tuple[ContactChannelView, ...]: ...


class ProvenanceRepository(Protocol):
    async def add(self, draft: ProvenanceDraft, *, now: datetime) -> ProvenanceView: ...

    async def get(self, provenance_id: UUID) -> ProvenanceView | None: ...


class ProspectUnitOfWork(Protocol):
    @property
    def prospects(self) -> ProspectRepository: ...

    @property
    def contacts(self) -> ContactRepository: ...

    @property
    def contact_channels(self) -> ContactChannelRepository: ...

    @property
    def provenance(self) -> ProvenanceRepository: ...

    @property
    def audit(self) -> AuditRecorder: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


type ProspectUnitOfWorkFactory = Callable[[TenantContext], ProspectUnitOfWork]


class GoogleSelectionGrantStore(Protocol):
    async def issue(self, place_ids: tuple[str, ...], owner: GoogleAccessOwner, *, now: datetime) -> str: ...

    async def resolve(self, token: str, owner: GoogleAccessOwner, *, now: datetime) -> tuple[str, ...]: ...
