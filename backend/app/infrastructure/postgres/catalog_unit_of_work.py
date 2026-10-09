from __future__ import annotations

from types import TracebackType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.errors import CatalogServiceUnavailable
from ...application.tenancy import ActorContext
from .actor_unit_of_work import SqlAlchemyActorUnitOfWork
from .audit_recorder import SqlAlchemyAuditRecorder
from .catalog_mutations import SqlAlchemyCatalogMutations


class SqlAlchemyCatalogAuditedUnitOfWork(SqlAlchemyActorUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], context: ActorContext) -> None:
        super().__init__(session_factory, context)
        self.mutations: SqlAlchemyCatalogMutations
        self.audit: SqlAlchemyAuditRecorder

    async def __aenter__(self) -> SqlAlchemyCatalogAuditedUnitOfWork:
        try:
            await super().__aenter__()
        except SQLAlchemyError as error:
            raise CatalogServiceUnavailable from error
        self.mutations = SqlAlchemyCatalogMutations(self.session)
        self.audit = SqlAlchemyAuditRecorder(self.session)
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        if exc_type is not None and issubclass(exc_type, SQLAlchemyError):
            raise CatalogServiceUnavailable from exc_value
