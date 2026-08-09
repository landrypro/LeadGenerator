from __future__ import annotations

from contextlib import suppress
from types import TracebackType

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.errors import AuditUnavailable
from ...application.tenancy import ActorContext, TenantContext
from ...domain.audit import AuditScope
from .actor_unit_of_work import SqlAlchemyActorUnitOfWork
from .audit_reader import SqlAlchemyAuditEventReader
from .tenant_unit_of_work import SqlAlchemyTenantUnitOfWork


class SqlAlchemyTenantAuditReadUnitOfWork(SqlAlchemyTenantUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], context: TenantContext) -> None:
        super().__init__(session_factory, context)
        self._audit_context = context
        self.reader: SqlAlchemyAuditEventReader

    async def __aenter__(self) -> SqlAlchemyTenantAuditReadUnitOfWork:
        try:
            await super().__aenter__()
            await self.session.execute(text("SELECT set_config('app.audit_scope', 'tenant', true)"))
        except SQLAlchemyError as error:
            await _safe_close(self)
            raise AuditUnavailable from error
        self.reader = SqlAlchemyAuditEventReader(
            self.session,
            scope=AuditScope.TENANT,
            organization_id=self._audit_context.organization_id,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        if exc_type is not None and issubclass(exc_type, SQLAlchemyError):
            raise AuditUnavailable from exc_value


class SqlAlchemyPlatformAuditReadUnitOfWork(SqlAlchemyActorUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], context: ActorContext) -> None:
        super().__init__(session_factory, context)
        self.reader: SqlAlchemyAuditEventReader

    async def __aenter__(self) -> SqlAlchemyPlatformAuditReadUnitOfWork:
        try:
            await super().__aenter__()
            await self.session.execute(
                text(
                    "SELECT "
                    "set_config('app.organization_id', '', true), "
                    "set_config('app.audit_scope', 'platform', true)"
                )
            )
        except SQLAlchemyError as error:
            await _safe_close(self)
            raise AuditUnavailable from error
        self.reader = SqlAlchemyAuditEventReader(self.session, scope=AuditScope.PLATFORM, organization_id=None)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        if exc_type is not None and issubclass(exc_type, SQLAlchemyError):
            raise AuditUnavailable from exc_value


async def _safe_close(unit_of_work: SqlAlchemyTenantUnitOfWork | SqlAlchemyActorUnitOfWork) -> None:
    with suppress(Exception):
        await unit_of_work.__aexit__(None, None, None)
