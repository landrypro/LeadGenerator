from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.ports.audit import AuditRecorder
from ...domain.audit import AuditEventDraft


class SqlAlchemyAuditRecorder(AuditRecorder):
    """Ajoute un audit dans la transaction SQLAlchemy fournie, sans la valider."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: AuditEventDraft) -> UUID:
        event_id = await self._session.scalar(
            text(
                """
                SELECT app_private.append_audit_event(
                    :id, :scope, :organization_id, :actor_kind, :actor_id, :action,
                    :entity_type, :entity_id, :request_id, :correlation_id, :source,
                    CAST(:metadata AS jsonb), :schema_version
                )
                """
            ),
            {
                "id": event.id,
                "scope": event.scope.value,
                "organization_id": event.organization_id,
                "actor_kind": event.actor_kind.value,
                "actor_id": event.actor_id,
                "action": event.action.value,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "request_id": event.request_id,
                "correlation_id": event.correlation_id,
                "source": event.source.value,
                "metadata": json.dumps(dict(event.metadata), ensure_ascii=True, separators=(",", ":")),
                "schema_version": event.schema_version,
            },
        )
        if not isinstance(event_id, UUID):
            raise RuntimeError("La primitive d’audit n’a pas retourné un UUID.")
        return event_id
