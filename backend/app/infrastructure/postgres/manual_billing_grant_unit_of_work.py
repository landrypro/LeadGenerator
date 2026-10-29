"""Unité de travail atomique pour les exceptions Billing sandbox."""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.errors import ManualBillingGrantUnavailable
from ...application.tenancy import ActorContext
from .actor_unit_of_work import SqlAlchemyActorUnitOfWork
from .audit_recorder import SqlAlchemyAuditRecorder
from .manual_billing_grants import SqlAlchemyManualBillingGrantMutations


class SqlAlchemyManualBillingGrantUnitOfWork(SqlAlchemyActorUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], context: ActorContext) -> None:
        super().__init__(session_factory, context)
        self.mutations: SqlAlchemyManualBillingGrantMutations
        self.audit: SqlAlchemyAuditRecorder

    async def __aenter__(self) -> SqlAlchemyManualBillingGrantUnitOfWork:
        try:
            await super().__aenter__()
        except SQLAlchemyError as error:
            raise ManualBillingGrantUnavailable from error
        self.mutations = SqlAlchemyManualBillingGrantMutations(self.session)
        self.audit = SqlAlchemyAuditRecorder(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        if exc_type is not None and issubclass(exc_type, SQLAlchemyError):
            raise ManualBillingGrantUnavailable from exc_value
