from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from ...application.ports.audit import AuditEventReader
from ...domain.audit import (
    AuditActorKind,
    AuditActorView,
    AuditEventFilter,
    AuditEventView,
    AuditScope,
    AuditSource,
)
from .models.audit import AuditEventModel
from .models.identity import UserModel


class SqlAlchemyAuditEventReader(AuditEventReader):
    def __init__(self, session: AsyncSession, *, scope: AuditScope, organization_id: UUID | None) -> None:
        self._session = session
        self._scope = scope
        self._organization_id = organization_id

    async def list_events(
        self,
        *,
        filters: AuditEventFilter,
        before_occurred_at: datetime | None,
        before_id: UUID | None,
        limit: int,
    ) -> tuple[AuditEventView, ...]:
        statement = (
            select(AuditEventModel, UserModel.display_name.label("actor_display_name"))
            .options(
                load_only(
                    AuditEventModel.id,
                    AuditEventModel.occurred_at,
                    AuditEventModel.action,
                    AuditEventModel.entity_type,
                    AuditEventModel.entity_id,
                    AuditEventModel.actor_kind,
                    AuditEventModel.actor_id,
                    AuditEventModel.request_id,
                    AuditEventModel.correlation_id,
                    AuditEventModel.source,
                    AuditEventModel.audit_metadata,
                    AuditEventModel.schema_version,
                )
            )
            .outerjoin(UserModel, UserModel.id == AuditEventModel.actor_id)
            .where(
                AuditEventModel.scope == self._scope.value,
                AuditEventModel.occurred_at >= filters.occurred_from,
                AuditEventModel.occurred_at < filters.occurred_to,
            )
            .order_by(AuditEventModel.occurred_at.desc(), AuditEventModel.id.desc())
            .limit(limit)
        )
        if self._scope is AuditScope.TENANT:
            statement = statement.where(AuditEventModel.organization_id == self._organization_id)
        if filters.action is not None:
            statement = statement.where(AuditEventModel.action == filters.action.value)
        if filters.entity_type is not None:
            statement = statement.where(AuditEventModel.entity_type == filters.entity_type)
        if filters.entity_id is not None:
            statement = statement.where(AuditEventModel.entity_id == filters.entity_id)
        if filters.actor_id is not None:
            statement = statement.where(AuditEventModel.actor_id == filters.actor_id)
        if before_occurred_at is not None and before_id is not None:
            statement = statement.where(
                or_(
                    AuditEventModel.occurred_at < before_occurred_at,
                    and_(AuditEventModel.occurred_at == before_occurred_at, AuditEventModel.id < before_id),
                )
            )

        rows = (await self._session.execute(statement)).all()
        return tuple(_to_view(model, display_name) for model, display_name in rows)


def _to_view(model: AuditEventModel, actor_display_name: str | None) -> AuditEventView:
    actor_kind = AuditActorKind(model.actor_kind)
    return AuditEventView(
        id=model.id,
        occurred_at=model.occurred_at,
        action=model.action,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        actor=AuditActorView(
            kind=actor_kind,
            id=model.actor_id,
            display_name=actor_display_name if actor_kind is AuditActorKind.USER else None,
        ),
        request_id=model.request_id,
        correlation_id=model.correlation_id,
        source=AuditSource(model.source),
        metadata=dict(model.audit_metadata),
        schema_version=model.schema_version,
    )
