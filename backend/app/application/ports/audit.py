from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from ...domain.audit import AuditEventDraft, AuditEventFilter, AuditEventView, AuditScope
from ..tenancy import ActorContext, InvitationAcceptanceContext, TenantContext
from .organization import ActorOrganizationMutationGateway, TenantOrganizationMutationGateway
from .provisioning import InvitationAcceptanceMutationGateway, PlatformProvisioningMutationGateway


class AuditRecorder(Protocol):
    async def record(self, event: AuditEventDraft) -> UUID: ...


class AuditEventReader(Protocol):
    async def list_events(
        self,
        *,
        filters: AuditEventFilter,
        before_occurred_at: datetime | None,
        before_id: UUID | None,
        limit: int,
    ) -> tuple[AuditEventView, ...]: ...


class AuditCursorCodec(Protocol):
    def encode(
        self,
        *,
        scope: AuditScope,
        organization_id: UUID | None,
        filters: AuditEventFilter,
        occurred_at: datetime,
        event_id: UUID,
    ) -> str: ...

    def decode(
        self,
        cursor: str | None,
        *,
        scope: AuditScope,
        organization_id: UUID | None,
        filters: AuditEventFilter,
    ) -> tuple[datetime | None, UUID | None]: ...


class AuditReadUnitOfWork(Protocol):
    @property
    def reader(self) -> AuditEventReader: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class _AuditedUnitOfWork(Protocol):
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


class TenantAuditedUnitOfWork(_AuditedUnitOfWork, Protocol):
    @property
    def mutations(self) -> TenantOrganizationMutationGateway: ...


class PlatformAuditedUnitOfWork(_AuditedUnitOfWork, Protocol):
    @property
    def mutations(self) -> PlatformProvisioningMutationGateway: ...


class ActorAuditedUnitOfWork(_AuditedUnitOfWork, Protocol):
    @property
    def mutations(self) -> ActorOrganizationMutationGateway: ...

    async def bind_tenant(self, context: TenantContext) -> None: ...


class InvitationAcceptanceUnitOfWork(_AuditedUnitOfWork, Protocol):
    @property
    def mutations(self) -> InvitationAcceptanceMutationGateway: ...

    async def bind_tenant(self, context: TenantContext) -> None: ...


type TenantAuditedUnitOfWorkFactory = Callable[[TenantContext], TenantAuditedUnitOfWork]
type PlatformAuditedUnitOfWorkFactory = Callable[[ActorContext], PlatformAuditedUnitOfWork]
type ActorAuditedUnitOfWorkFactory = Callable[[ActorContext], ActorAuditedUnitOfWork]
type InvitationAcceptanceUnitOfWorkFactory = Callable[[InvitationAcceptanceContext], InvitationAcceptanceUnitOfWork]
type TenantAuditReadUnitOfWorkFactory = Callable[[TenantContext], AuditReadUnitOfWork]
type PlatformAuditReadUnitOfWorkFactory = Callable[[ActorContext], AuditReadUnitOfWork]
