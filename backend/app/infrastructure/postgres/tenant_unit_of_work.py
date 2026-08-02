from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.tenancy import TenantContext
from .unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyTenantUnitOfWork(SqlAlchemyUnitOfWork):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        context: TenantContext,
    ) -> None:
        super().__init__(session_factory)
        self._context = context

    async def __aenter__(self) -> SqlAlchemyTenantUnitOfWork:
        await super().__aenter__()
        try:
            await self.session.execute(
                text(
                    """
                    SELECT
                        set_config('app.actor_id', :actor_id, true),
                        set_config('app.organization_id', :organization_id, true),
                        set_config('app.request_id', :request_id, true)
                    """
                ),
                {
                    "actor_id": str(self._context.actor_id),
                    "organization_id": str(self._context.organization_id),
                    "request_id": self._context.request_id,
                },
            )
        except Exception:
            await super().__aexit__(None, None, None)
            raise
        return self
