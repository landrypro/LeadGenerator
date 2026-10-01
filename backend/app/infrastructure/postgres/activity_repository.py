from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.ports.activity import ActivityRepository, TaskEventRepository, TaskRepository
from ...domain.activity import (
    ActivityDirection,
    ActivityType,
    ContactPermissionSnapshot,
    ProspectActivityDraft,
    ProspectActivityView,
    ProspectTaskDraft,
    ProspectTaskEventView,
    ProspectTaskView,
    TaskEventType,
    TaskPriority,
    TaskStatus,
)


class SqlAlchemyActivityRepository(ActivityRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, draft: ProspectActivityDraft, *, organization_id: UUID, actor_id: UUID, now: datetime
    ) -> ProspectActivityView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.prospect_activities (
                            id, organization_id, prospect_id, actor_id, activity_type, direction, summary, note,
                            occurred_at, contact_id, contact_channel_id, permission_snapshot,
                            correction_of_activity_id, correction_reason, idempotency_key, command_fingerprint, created_at
                        ) VALUES (
                            :id, :organization_id, :prospect_id, :actor_id, :activity_type, :direction, :summary, :note,
                            :occurred_at, :contact_id, :contact_channel_id, :permission_snapshot,
                            :correction_of_activity_id, :correction_reason, :idempotency_key, :command_fingerprint, :now
                        ) RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": organization_id,
                        "prospect_id": draft.prospect_id,
                        "actor_id": actor_id,
                        "activity_type": draft.activity_type.value,
                        "direction": draft.direction.value,
                        "summary": draft.summary,
                        "note": draft.note,
                        "occurred_at": draft.occurred_at,
                        "contact_id": draft.contact_id,
                        "contact_channel_id": draft.contact_channel_id,
                        "permission_snapshot": draft.permission_snapshot.value,
                        "correction_of_activity_id": draft.correction_of_activity_id,
                        "correction_reason": draft.correction_reason,
                        "idempotency_key": draft.idempotency_key,
                        "command_fingerprint": draft.command_fingerprint,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _activity_from_row(cast(Mapping[str, object], row))

    async def get(self, activity_id: UUID) -> ProspectActivityView | None:
        row = (
            (
                await self._session.execute(
                    text("SELECT * FROM public.prospect_activities WHERE id = :id"), {"id": activity_id}
                )
            )
            .mappings()
            .one_or_none()
        )
        return _activity_from_row(cast(Mapping[str, object], row)) if row else None

    async def get_by_idempotency_key(self, prospect_id: UUID, idempotency_key: str) -> ProspectActivityView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.prospect_activities
                        WHERE prospect_id = :prospect_id AND idempotency_key = :idempotency_key
                        """
                    ),
                    {"prospect_id": prospect_id, "idempotency_key": idempotency_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _activity_from_row(cast(Mapping[str, object], row)) if row else None

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[ProspectActivityView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.prospect_activities
                        WHERE prospect_id = :prospect_id
                        ORDER BY occurred_at DESC, id DESC LIMIT :limit
                        """
                    ),
                    {"prospect_id": prospect_id, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_activity_from_row(cast(Mapping[str, object], row)) for row in rows)


class SqlAlchemyTaskRepository(TaskRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, draft: ProspectTaskDraft, *, organization_id: UUID, actor_id: UUID, now: datetime
    ) -> ProspectTaskView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.prospect_tasks (
                            id, organization_id, prospect_id, created_by, assigned_membership_id,
                            title, description, priority, status, due_at, reminder_at, idempotency_key,
                            command_fingerprint, created_at, updated_at
                        ) VALUES (
                            :id, :organization_id, :prospect_id, :created_by, :assigned_membership_id,
                            :title, :description, :priority, 'open', :due_at, :reminder_at, :idempotency_key,
                            :command_fingerprint, :now, :now
                        ) RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": organization_id,
                        "prospect_id": draft.prospect_id,
                        "created_by": actor_id,
                        "assigned_membership_id": draft.assigned_membership_id,
                        "title": draft.title,
                        "description": draft.description,
                        "priority": draft.priority.value,
                        "due_at": draft.due_at,
                        "reminder_at": draft.reminder_at,
                        "idempotency_key": draft.idempotency_key,
                        "command_fingerprint": draft.command_fingerprint,
                        "now": now,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _task_from_row(cast(Mapping[str, object], row))

    async def get(self, task_id: UUID) -> ProspectTaskView | None:
        row = (
            (await self._session.execute(text(_task_select("WHERE prospect_tasks.id = :id")), {"id": task_id}))
            .mappings()
            .one_or_none()
        )
        return _task_from_row(cast(Mapping[str, object], row)) if row else None

    async def get_by_idempotency_key(self, prospect_id: UUID, idempotency_key: str) -> ProspectTaskView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        _task_select(
                            "WHERE prospect_tasks.prospect_id = :prospect_id "
                            "AND prospect_tasks.idempotency_key = :idempotency_key"
                        )
                    ),
                    {"prospect_id": prospect_id, "idempotency_key": idempotency_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _task_from_row(cast(Mapping[str, object], row)) if row else None

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[ProspectTaskView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        _task_select(
                            "WHERE prospect_tasks.prospect_id = :prospect_id "
                            "ORDER BY prospect_tasks.due_at ASC, prospect_tasks.id ASC LIMIT :limit"
                        )
                    ),
                    {"prospect_id": prospect_id, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_task_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def list(
        self,
        *,
        limit: int,
        assigned_membership_id: UUID | None = None,
        prospect_id: UUID | None = None,
        status: str | None = None,
        due_before: datetime | None = None,
    ) -> tuple[ProspectTaskView, ...]:
        clauses = ["1 = 1"]
        parameters: dict[str, object] = {"limit": limit}
        for key, value, clause in (
            (
                "assigned_membership_id",
                assigned_membership_id,
                "prospect_tasks.assigned_membership_id = :assigned_membership_id",
            ),
            ("prospect_id", prospect_id, "prospect_tasks.prospect_id = :prospect_id"),
            ("status", status, "prospect_tasks.status = :status"),
            ("due_before", due_before, "prospect_tasks.due_at <= :due_before"),
        ):
            if value is not None:
                clauses.append(clause)
                parameters[key] = value
        rows = (
            (
                await self._session.execute(
                    text(
                        _task_select(
                            "WHERE "
                            + " AND ".join(clauses)
                            + " ORDER BY prospect_tasks.due_at ASC, prospect_tasks.id ASC LIMIT :limit"
                        )
                    ),
                    parameters,
                )
            )
            .mappings()
            .all()
        )
        return tuple(_task_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def update(
        self,
        task_id: UUID,
        *,
        expected_version: int,
        changes: dict[str, object],
        now: datetime,
    ) -> ProspectTaskView | None:
        allowed = {
            "assigned_membership_id",
            "title",
            "description",
            "priority",
            "status",
            "due_at",
            "reminder_at",
            "reminder_acknowledged_at",
            "reminder_snoozed_until",
            "completed_at",
            "cancelled_at",
            "cancelled_reason",
        }
        fields = {name: value for name, value in changes.items() if name in allowed}
        if not fields:
            return await self.get(task_id)
        assignments = [f"{name} = :{name}" for name in fields]
        assignments.extend(["updated_at = :now", "version = version + 1"])
        row = (
            (
                await self._session.execute(
                    text(
                        "UPDATE public.prospect_tasks SET "
                        + ", ".join(assignments)
                        + " WHERE id = :id AND version = :expected_version RETURNING *"
                    ),
                    {**fields, "id": task_id, "expected_version": expected_version, "now": now},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _task_from_row(cast(Mapping[str, object], row)) if row else None

    async def list_due_reminders(
        self, *, now: datetime, limit: int, assigned_membership_id: UUID | None = None
    ) -> tuple[ProspectTaskView, ...]:
        clauses = [
            "prospect_tasks.status = 'open'",
            "prospect_tasks.reminder_at IS NOT NULL",
            "prospect_tasks.reminder_at <= :now",
            "prospect_tasks.reminder_acknowledged_at IS NULL",
            "(prospect_tasks.reminder_snoozed_until IS NULL OR prospect_tasks.reminder_snoozed_until <= :now)",
        ]
        parameters: dict[str, object] = {"now": now, "limit": limit}
        if assigned_membership_id is not None:
            clauses.append("prospect_tasks.assigned_membership_id = :assigned_membership_id")
            parameters["assigned_membership_id"] = assigned_membership_id
        rows = (
            (
                await self._session.execute(
                    text(
                        _task_select(
                            "WHERE "
                            + " AND ".join(clauses)
                            + " ORDER BY prospect_tasks.reminder_at ASC, prospect_tasks.id ASC LIMIT :limit"
                        )
                    ),
                    parameters,
                )
            )
            .mappings()
            .all()
        )
        return tuple(_task_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def get_next_action(self, prospect_id: UUID) -> ProspectTaskView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        _task_select(
                            "WHERE prospect_tasks.prospect_id = :prospect_id AND prospect_tasks.status = 'open' "
                            "ORDER BY prospect_tasks.due_at ASC, "
                            "CASE prospect_tasks.priority WHEN 'urgent' THEN 4 WHEN 'high' THEN 3 "
                            "WHEN 'normal' THEN 2 ELSE 1 END DESC, prospect_tasks.id ASC LIMIT 1"
                        )
                    ),
                    {"prospect_id": prospect_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _task_from_row(cast(Mapping[str, object], row)) if row else None

    async def list_next_actions(self, *, limit: int) -> tuple[ProspectTaskView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT DISTINCT ON (prospect_tasks.prospect_id)
                            prospect_tasks.*,
                            COALESCE(memberships.status = 'active', true) AS assigned_membership_is_active
                        FROM public.prospect_tasks
                        LEFT JOIN public.memberships ON memberships.id = prospect_tasks.assigned_membership_id
                        WHERE prospect_tasks.status = 'open'
                        ORDER BY prospect_tasks.prospect_id, prospect_tasks.due_at ASC,
                                 CASE prospect_tasks.priority WHEN 'urgent' THEN 4 WHEN 'high' THEN 3
                                 WHEN 'normal' THEN 2 ELSE 1 END DESC, prospect_tasks.id ASC
                        LIMIT :limit
                        """
                    ),
                    {"limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_task_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def is_active_assignee(self, membership_id: UUID) -> bool:
        return bool(
            (
                await self._session.execute(
                    text("SELECT EXISTS(SELECT 1 FROM public.memberships WHERE id = :id AND status = 'active')"),
                    {"id": membership_id},
                )
            ).scalar_one()
        )


class SqlAlchemyTaskEventRepository(TaskEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: ProspectTaskEventView) -> ProspectTaskEventView:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        INSERT INTO public.prospect_task_events (
                            id, organization_id, prospect_id, task_id, actor_id, event_type,
                            resulting_status, resulting_version, changed_fields, reason, occurred_at,
                            idempotency_key, command_fingerprint
                        ) VALUES (
                            :id, :organization_id, :prospect_id, :task_id, :actor_id, :event_type,
                            :resulting_status, :resulting_version, CAST(:changed_fields AS jsonb), :reason, :occurred_at,
                            :idempotency_key, :command_fingerprint
                        ) RETURNING *
                        """
                    ),
                    {
                        "id": event.id,
                        "organization_id": event.organization_id,
                        "prospect_id": event.prospect_id,
                        "task_id": event.task_id,
                        "actor_id": event.actor_id,
                        "event_type": event.event_type.value,
                        "resulting_status": event.resulting_status.value,
                        "resulting_version": event.resulting_version,
                        "changed_fields": json.dumps(event.changed_fields),
                        "reason": event.reason,
                        "occurred_at": event.occurred_at,
                        "idempotency_key": event.idempotency_key,
                        "command_fingerprint": event.command_fingerprint,
                    },
                )
            )
            .mappings()
            .one()
        )
        return _task_event_from_row(cast(Mapping[str, object], row))

    async def get_by_idempotency_key(self, task_id: UUID, idempotency_key: str) -> ProspectTaskEventView | None:
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.prospect_task_events
                        WHERE task_id = :task_id AND idempotency_key = :idempotency_key
                        """
                    ),
                    {"task_id": task_id, "idempotency_key": idempotency_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        return _task_event_from_row(cast(Mapping[str, object], row)) if row else None

    async def list_for_task(self, task_id: UUID, *, limit: int) -> tuple[ProspectTaskEventView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.prospect_task_events
                        WHERE task_id = :task_id
                        ORDER BY occurred_at ASC, id ASC LIMIT :limit
                        """
                    ),
                    {"task_id": task_id, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_task_event_from_row(cast(Mapping[str, object], row)) for row in rows)

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[ProspectTaskEventView, ...]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        SELECT * FROM public.prospect_task_events
                        WHERE prospect_id = :prospect_id
                        ORDER BY occurred_at DESC, id DESC LIMIT :limit
                        """
                    ),
                    {"prospect_id": prospect_id, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return tuple(_task_event_from_row(cast(Mapping[str, object], row)) for row in rows)


def _activity_from_row(row: Mapping[str, object]) -> ProspectActivityView:
    return ProspectActivityView(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        prospect_id=cast(UUID, row["prospect_id"]),
        actor_id=cast(UUID, row["actor_id"]),
        activity_type=ActivityType(str(row["activity_type"])),
        direction=ActivityDirection(str(row["direction"])),
        summary=str(row["summary"]),
        occurred_at=cast(datetime, row["occurred_at"]),
        created_at=cast(datetime, row["created_at"]),
        note=cast(str | None, row["note"]),
        contact_id=cast(UUID | None, row["contact_id"]),
        contact_channel_id=cast(UUID | None, row["contact_channel_id"]),
        permission_snapshot=ContactPermissionSnapshot(str(row["permission_snapshot"])),
        correction_of_activity_id=cast(UUID | None, row["correction_of_activity_id"]),
        correction_reason=cast(str | None, row["correction_reason"]),
        idempotency_key=cast(str | None, row["idempotency_key"]),
        command_fingerprint=cast(str | None, row["command_fingerprint"]),
    )


def _task_from_row(row: Mapping[str, object]) -> ProspectTaskView:
    return ProspectTaskView(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        prospect_id=cast(UUID, row["prospect_id"]),
        created_by=cast(UUID, row["created_by"]),
        assigned_membership_id=cast(UUID | None, row["assigned_membership_id"]),
        title=str(row["title"]),
        due_at=cast(datetime, row["due_at"]),
        priority=TaskPriority(str(row["priority"])),
        status=TaskStatus(str(row["status"])),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
        version=int(cast(int, row["version"])),
        description=cast(str | None, row["description"]),
        reminder_at=cast(datetime | None, row["reminder_at"]),
        reminder_acknowledged_at=cast(datetime | None, row["reminder_acknowledged_at"]),
        reminder_snoozed_until=cast(datetime | None, row["reminder_snoozed_until"]),
        completed_at=cast(datetime | None, row["completed_at"]),
        cancelled_at=cast(datetime | None, row["cancelled_at"]),
        cancelled_reason=cast(str | None, row["cancelled_reason"]),
        idempotency_key=cast(str | None, row["idempotency_key"]),
        command_fingerprint=cast(str | None, row["command_fingerprint"]),
        assigned_membership_is_active=bool(row.get("assigned_membership_is_active", True)),
    )


def _task_select(suffix: str) -> str:
    """Return task rows enriched with the assignment state without exposing membership data."""
    return (
        """
        SELECT prospect_tasks.*,
               COALESCE(memberships.status = 'active', true) AS assigned_membership_is_active
        FROM public.prospect_tasks
        LEFT JOIN public.memberships ON memberships.id = prospect_tasks.assigned_membership_id
    """
        + suffix
    )


def _task_event_from_row(row: Mapping[str, object]) -> ProspectTaskEventView:
    return ProspectTaskEventView(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        prospect_id=cast(UUID, row["prospect_id"]),
        task_id=cast(UUID, row["task_id"]),
        actor_id=cast(UUID, row["actor_id"]),
        event_type=TaskEventType(str(row["event_type"])),
        occurred_at=cast(datetime, row["occurred_at"]),
        resulting_status=TaskStatus(str(row["resulting_status"])),
        resulting_version=int(cast(int, row["resulting_version"])),
        changed_fields=dict(cast(Mapping[str, str], row["changed_fields"])),
        reason=cast(str | None, row["reason"]),
        idempotency_key=cast(str | None, row["idempotency_key"]),
        command_fingerprint=cast(str | None, row["command_fingerprint"]),
    )
