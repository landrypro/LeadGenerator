from __future__ import annotations

from types import TracebackType

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.errors import OrganizationAdministrationUnavailable, ProvisioningServiceUnavailable
from ...application.tenancy import ActorContext, InvitationAcceptanceContext, TenantContext
from .actor_unit_of_work import SqlAlchemyActorUnitOfWork
from .audit_recorder import SqlAlchemyAuditRecorder
from .organization_mutations import SqlAlchemyActorOrganizationMutations, SqlAlchemyTenantOrganizationMutations
from .provisioning_mutations import SqlAlchemyInvitationAcceptanceMutations, SqlAlchemyPlatformProvisioningMutations
from .tenant_unit_of_work import SqlAlchemyTenantUnitOfWork
from .unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyTenantAuditedUnitOfWork(SqlAlchemyTenantUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], context: TenantContext) -> None:
        super().__init__(session_factory, context)
        self.mutations: SqlAlchemyTenantOrganizationMutations
        self.audit: SqlAlchemyAuditRecorder

    async def __aenter__(self) -> SqlAlchemyTenantAuditedUnitOfWork:
        try:
            await super().__aenter__()
        except SQLAlchemyError as error:
            raise OrganizationAdministrationUnavailable from error
        self.mutations = SqlAlchemyTenantOrganizationMutations(self.session)
        self.audit = SqlAlchemyAuditRecorder(self.session)
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        if exc_type is not None and issubclass(exc_type, SQLAlchemyError):
            raise OrganizationAdministrationUnavailable from exc_value


class SqlAlchemyPlatformAuditedUnitOfWork(SqlAlchemyActorUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], context: ActorContext) -> None:
        super().__init__(session_factory, context)
        self.mutations: SqlAlchemyPlatformProvisioningMutations
        self.audit: SqlAlchemyAuditRecorder

    async def __aenter__(self) -> SqlAlchemyPlatformAuditedUnitOfWork:
        try:
            await super().__aenter__()
        except SQLAlchemyError as error:
            raise ProvisioningServiceUnavailable from error
        self.mutations = SqlAlchemyPlatformProvisioningMutations(self.session)
        self.audit = SqlAlchemyAuditRecorder(self.session)
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        if exc_type is not None and issubclass(exc_type, SQLAlchemyError):
            raise ProvisioningServiceUnavailable from exc_value


class SqlAlchemyActorAuditedUnitOfWork(SqlAlchemyActorUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], context: ActorContext) -> None:
        super().__init__(session_factory, context)
        self.mutations: SqlAlchemyActorOrganizationMutations
        self.audit: SqlAlchemyAuditRecorder

    async def __aenter__(self) -> SqlAlchemyActorAuditedUnitOfWork:
        try:
            await super().__aenter__()
        except SQLAlchemyError as error:
            raise OrganizationAdministrationUnavailable from error
        self.mutations = SqlAlchemyActorOrganizationMutations(self.session)
        self.audit = SqlAlchemyAuditRecorder(self.session)
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        if exc_type is not None and issubclass(exc_type, SQLAlchemyError):
            raise OrganizationAdministrationUnavailable from exc_value

    async def bind_tenant(self, context: TenantContext) -> None:
        await _bind_tenant(self.session, context)


class SqlAlchemyInvitationAcceptanceUnitOfWork(SqlAlchemyUnitOfWork):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        context: InvitationAcceptanceContext,
    ) -> None:
        super().__init__(session_factory)
        self._context = context
        self.mutations: SqlAlchemyInvitationAcceptanceMutations
        self.audit: SqlAlchemyAuditRecorder

    async def __aenter__(self) -> SqlAlchemyInvitationAcceptanceUnitOfWork:
        try:
            await super().__aenter__()
        except SQLAlchemyError as error:
            raise ProvisioningServiceUnavailable from error
        try:
            await self.session.execute(
                text(
                    """
                    SELECT set_config('app.request_id', :request_id, true),
                           set_config('app.actor_id', :actor_id, true)
                    """
                ),
                {
                    "request_id": self._context.request_id,
                    "actor_id": str(self._context.actor_id) if self._context.actor_id else "",
                },
            )
        except Exception:
            await super().__aexit__(None, None, None)
            raise
        self.mutations = SqlAlchemyInvitationAcceptanceMutations(self.session)
        self.audit = SqlAlchemyAuditRecorder(self.session)
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        if exc_type is not None and issubclass(exc_type, SQLAlchemyError):
            raise ProvisioningServiceUnavailable from exc_value

    async def bind_tenant(self, context: TenantContext) -> None:
        await _bind_tenant(self.session, context)


async def _bind_tenant(session: AsyncSession, context: TenantContext) -> None:
    await session.execute(
        text(
            """
            SELECT set_config('app.actor_id', :actor_id, true),
                   set_config('app.organization_id', :organization_id, true),
                   set_config('app.request_id', :request_id, true)
            """
        ),
        {
            "actor_id": str(context.actor_id),
            "organization_id": str(context.organization_id),
            "request_id": context.request_id,
        },
    )
