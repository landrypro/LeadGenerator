from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._completed = False

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("L’unité de travail n’est pas active.")
        if self._completed:
            raise RuntimeError("L’unité de travail est déjà terminée.")
        return self._session

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        if self._session is not None:
            raise RuntimeError("Une unité de travail ne peut pas être réutilisée simultanément.")
        self._session = self._session_factory()
        await self._session.begin()
        self._completed = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        session = self._session
        if session is None:
            return
        try:
            if session.in_transaction():
                await session.rollback()
        finally:
            await session.close()
            self._session = None
            self._completed = False

    async def commit(self) -> None:
        session = self.session
        if self._completed:
            raise RuntimeError("L’unité de travail est déjà terminée.")
        await session.commit()
        self._completed = True

    async def rollback(self) -> None:
        session = self.session
        if self._completed:
            raise RuntimeError("L’unité de travail est déjà terminée.")
        await session.rollback()
        self._completed = True
