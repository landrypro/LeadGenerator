from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from ...domain.audit import (
    AuditAction,
    AuditEventFilter,
    AuditEventView,
    AuditScope,
    audit_action_matches_scope,
    audit_entity_type_for_action,
    audit_entity_types_for_scope,
)
from ..errors import InsufficientCapability
from ..ports.audit import (
    AuditCursorCodec,
    AuditReadUnitOfWork,
    PlatformAuditReadUnitOfWorkFactory,
    TenantAuditReadUnitOfWorkFactory,
)
from ..ports.clock import Clock
from ..tenancy import ActorContext, TenantContext

DEFAULT_AUDIT_DAYS = 30
MAX_AUDIT_DAYS = 90


@dataclass(frozen=True, slots=True)
class AuditEventPage:
    items: tuple[AuditEventView, ...]
    next_cursor: str | None
    occurred_from: datetime
    occurred_to: datetime


class _ListAuditEventsUseCase[ContextT]:
    def __init__(
        self,
        *,
        scope: AuditScope,
        required_capability: str,
        unit_of_work_factory: Callable[[ContextT], AuditReadUnitOfWork],
        cursor_codec: AuditCursorCodec,
        clock: Clock,
    ) -> None:
        self._scope = scope
        self._required_capability = required_capability
        self._unit_of_work_factory = unit_of_work_factory
        self._cursor_codec = cursor_codec
        self._clock = clock

    async def execute(
        self,
        *,
        context: ContextT,
        has_capability: bool,
        cursor: str | None,
        limit: int,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> AuditEventPage:
        if not has_capability:
            raise InsufficientCapability(self._required_capability)
        if not 1 <= limit <= 100:
            raise ValueError("La limite d’audit doit être comprise entre 1 et 100.")
        filters = _filters(
            scope=self._scope,
            now=self._clock.now(),
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
        )
        organization_id = context.organization_id if isinstance(context, TenantContext) else None
        before_occurred_at, before_id = self._cursor_codec.decode(
            cursor,
            scope=self._scope,
            organization_id=organization_id,
            filters=filters,
        )
        async with self._unit_of_work_factory(context) as unit_of_work:
            rows = await unit_of_work.reader.list_events(
                filters=filters,
                before_occurred_at=before_occurred_at,
                before_id=before_id,
                limit=limit + 1,
            )
        items = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = items[-1]
            next_cursor = self._cursor_codec.encode(
                scope=self._scope,
                organization_id=organization_id,
                filters=filters,
                occurred_at=last.occurred_at,
                event_id=last.id,
            )
        return AuditEventPage(
            items=items,
            next_cursor=next_cursor,
            occurred_from=filters.occurred_from,
            occurred_to=filters.occurred_to,
        )


class ListTenantAuditEventsUseCase(_ListAuditEventsUseCase[TenantContext]):
    def __init__(
        self,
        unit_of_work_factory: TenantAuditReadUnitOfWorkFactory,
        cursor_codec: AuditCursorCodec,
        clock: Clock,
    ) -> None:
        super().__init__(
            scope=AuditScope.TENANT,
            required_capability="audit:read",
            unit_of_work_factory=unit_of_work_factory,
            cursor_codec=cursor_codec,
            clock=clock,
        )


class ListPlatformAuditEventsUseCase(_ListAuditEventsUseCase[ActorContext]):
    def __init__(
        self,
        unit_of_work_factory: PlatformAuditReadUnitOfWorkFactory,
        cursor_codec: AuditCursorCodec,
        clock: Clock,
    ) -> None:
        super().__init__(
            scope=AuditScope.PLATFORM,
            required_capability="platform:audit:read",
            unit_of_work_factory=unit_of_work_factory,
            cursor_codec=cursor_codec,
            clock=clock,
        )


def _filters(
    *,
    scope: AuditScope,
    now: datetime,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    action: str | None,
    entity_type: str | None,
    entity_id: UUID | None,
    actor_id: UUID | None,
) -> AuditEventFilter:
    if now.tzinfo is None:
        raise ValueError("L’horloge d’audit doit retourner une date avec fuseau.")
    if (occurred_from is None) != (occurred_to is None):
        raise ValueError("Les deux bornes temporelles sont obligatoires.")
    upper = occurred_to or now
    lower = occurred_from or (upper - timedelta(days=DEFAULT_AUDIT_DAYS))
    if lower.tzinfo is None or upper.tzinfo is None or lower.utcoffset() is None or upper.utcoffset() is None:
        raise ValueError("Les dates d’audit doivent inclure un fuseau horaire.")
    lower = lower.astimezone(UTC)
    upper = upper.astimezone(UTC)
    if lower >= upper:
        raise ValueError("La période d’audit est invalide.")
    if upper - lower > timedelta(days=MAX_AUDIT_DAYS):
        raise ValueError("La période d’audit ne peut pas dépasser 90 jours.")

    parsed_action = None
    if action is not None:
        try:
            parsed_action = AuditAction(action)
        except ValueError as error:
            raise ValueError("Le code d’action d’audit est inconnu.") from error
        if not audit_action_matches_scope(parsed_action, scope):
            raise ValueError("L’action d’audit n’appartient pas à cette portée.")

    allowed_entity_types = audit_entity_types_for_scope(scope)
    if entity_type is not None and entity_type not in allowed_entity_types:
        raise ValueError("Le type d’entité d’audit est inconnu.")
    if entity_id is not None and entity_type is None:
        raise ValueError("entity_type est obligatoire avec entity_id.")
    if (
        parsed_action is not None
        and entity_type is not None
        and audit_entity_type_for_action(parsed_action) != entity_type
    ):
        raise ValueError("Le type d’entité ne correspond pas à l’action.")

    return AuditEventFilter(
        occurred_from=lower,
        occurred_to=upper,
        action=parsed_action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
    )
