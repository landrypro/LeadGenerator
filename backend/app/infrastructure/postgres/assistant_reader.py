from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.ports.assistant import AssistantScopeReader, AssistantScopeSnapshot
from ...application.tenancy import TenantContext
from ...domain.assistant import AssistantIntentCode, AssistantScopeKind
from .tenant_unit_of_work import SqlAlchemyTenantUnitOfWork


class PostgresAssistantScopeReader(AssistantScopeReader):
    """Projection strictement en lecture seule sous contexte RLS."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def organization_enabled(self, context: TenantContext) -> bool:
        async with SqlAlchemyTenantUnitOfWork(self._session_factory, context, snapshot_readonly=True) as unit:
            result = await unit.session.execute(
                text("""
                    SELECT coalesce(bool_or(automation_enabled), false)
                    FROM automation_organization_settings
                    WHERE organization_id = :org
                """),
                {"org": context.organization_id},
            )
            return bool(result.scalar_one())

    async def resolve(
        self,
        context: TenantContext,
        *,
        membership_id: UUID,
        intent_code: AssistantIntentCode,
        scope_kind: AssistantScopeKind,
        collective: bool,
    ) -> AssistantScopeSnapshot:
        del intent_code
        params = {
            "org": context.organization_id,
            "owner": membership_id,
            "collective": collective,
            "new_only": scope_kind == AssistantScopeKind.NEW_PROSPECTS,
        }
        async with SqlAlchemyTenantUnitOfWork(self._session_factory, context, snapshot_readonly=True) as unit:
            enabled_result = await unit.session.execute(
                text("""
                    SELECT coalesce(bool_or(automation_enabled), false)
                    FROM automation_organization_settings WHERE organization_id = :org
                """),
                params,
            )
            enabled = bool(enabled_result.scalar_one())
            if scope_kind in {AssistantScopeKind.NONE, AssistantScopeKind.AUTOMATION_STATUS}:
                return AssistantScopeSnapshot(resolved_count=None, organization_enabled=enabled)
            count_result = await unit.session.execute(
                text("""
                    SELECT count(*) FROM prospects
                    WHERE organization_id = :org AND archived_at IS NULL
                      AND stage_code NOT IN ('won', 'lost', 'archived')
                      AND (NOT :new_only OR stage_code = 'new')
                      AND (:collective OR owner_id = :owner)
                """),
                params,
            )
            return AssistantScopeSnapshot(resolved_count=int(count_result.scalar_one()), organization_enabled=enabled)
