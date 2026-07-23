from __future__ import annotations

from types import TracebackType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.errors import AuthenticationServiceUnavailable
from .identity_repository import SqlAlchemyIdentityRepository
from .unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyIdentityUnitOfWork(SqlAlchemyUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(session_factory)
        self._identities: SqlAlchemyIdentityRepository | None = None

    @property
    def identities(self) -> SqlAlchemyIdentityRepository:
        if self._identities is None:
            raise RuntimeError("L’unité de travail d’identité n’est pas active.")
        return self._identities

    async def __aenter__(self) -> SqlAlchemyIdentityUnitOfWork:
        try:
            await super().__aenter__()
        except SQLAlchemyError as error:
            raise AuthenticationServiceUnavailable from error
        self._identities = SqlAlchemyIdentityRepository(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            try:
                await super().__aexit__(exc_type, exc_value, traceback)
            except SQLAlchemyError as error:
                raise AuthenticationServiceUnavailable from error
            if isinstance(exc_value, SQLAlchemyError):
                raise AuthenticationServiceUnavailable from exc_value
        finally:
            self._identities = None
