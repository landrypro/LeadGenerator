import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from backend.app.application.ports.health import DependencyHealth
from backend.app.application.tenancy import ActorContext, InvitationAcceptanceContext, TenantContext

from .actor_unit_of_work import SqlAlchemyActorUnitOfWork
from .audit_read_unit_of_work import SqlAlchemyPlatformAuditReadUnitOfWork, SqlAlchemyTenantAuditReadUnitOfWork
from .audited_unit_of_work import (
    SqlAlchemyActorAuditedUnitOfWork,
    SqlAlchemyInvitationAcceptanceUnitOfWork,
    SqlAlchemyPlatformAuditedUnitOfWork,
    SqlAlchemyTenantAuditedUnitOfWork,
)
from .identity_unit_of_work import SqlAlchemyIdentityUnitOfWork
from .tenant_unit_of_work import SqlAlchemyTenantUnitOfWork
from .unit_of_work import SqlAlchemyUnitOfWork

LOGGER = logging.getLogger(__name__)


class PostgresDatabase:
    def __init__(
        self,
        url: str,
        *,
        connect_timeout_seconds: float,
        pool_size: int,
        max_overflow: int,
        pool_timeout_seconds: float,
        statement_timeout_ms: int,
    ) -> None:
        self._connect_timeout_seconds = connect_timeout_seconds
        self._engine = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout_seconds,
            connect_args={
                "timeout": connect_timeout_seconds,
                "server_settings": {
                    "application_name": "prospect-crm",
                    "statement_timeout": str(statement_timeout_ms),
                },
            },
        )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def name(self) -> str:
        return "postgresql"

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    def unit_of_work(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)

    def identity_unit_of_work(self) -> SqlAlchemyIdentityUnitOfWork:
        return SqlAlchemyIdentityUnitOfWork(self._session_factory)

    def tenant_unit_of_work(self, context: TenantContext) -> SqlAlchemyTenantUnitOfWork:
        return SqlAlchemyTenantUnitOfWork(self._session_factory, context)

    def actor_unit_of_work(self, context: ActorContext) -> SqlAlchemyActorUnitOfWork:
        return SqlAlchemyActorUnitOfWork(self._session_factory, context)

    def tenant_audited_unit_of_work(self, context: TenantContext) -> SqlAlchemyTenantAuditedUnitOfWork:
        return SqlAlchemyTenantAuditedUnitOfWork(self._session_factory, context)

    def platform_audited_unit_of_work(self, context: ActorContext) -> SqlAlchemyPlatformAuditedUnitOfWork:
        return SqlAlchemyPlatformAuditedUnitOfWork(self._session_factory, context)

    def actor_audited_unit_of_work(self, context: ActorContext) -> SqlAlchemyActorAuditedUnitOfWork:
        return SqlAlchemyActorAuditedUnitOfWork(self._session_factory, context)

    def invitation_acceptance_unit_of_work(
        self, context: InvitationAcceptanceContext
    ) -> SqlAlchemyInvitationAcceptanceUnitOfWork:
        return SqlAlchemyInvitationAcceptanceUnitOfWork(self._session_factory, context)

    def tenant_audit_read_unit_of_work(self, context: TenantContext) -> SqlAlchemyTenantAuditReadUnitOfWork:
        return SqlAlchemyTenantAuditReadUnitOfWork(self._session_factory, context)

    def platform_audit_read_unit_of_work(self, context: ActorContext) -> SqlAlchemyPlatformAuditReadUnitOfWork:
        return SqlAlchemyPlatformAuditReadUnitOfWork(self._session_factory, context)

    async def check(self) -> DependencyHealth:
        try:
            async with asyncio.timeout(self._connect_timeout_seconds):
                async with self._engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
        except Exception as error:
            LOGGER.warning("PostgreSQL readiness probe failed (%s).", type(error).__name__)
            return DependencyHealth(name=self.name, state="unavailable")
        return DependencyHealth(name=self.name, state="ok")

    async def close(self) -> None:
        await self._engine.dispose()
