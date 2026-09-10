from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...domain.activity import (
    ProspectActivityDraft,
    ProspectActivityView,
    ProspectTaskDraft,
    ProspectTaskEventView,
    ProspectTaskView,
)


class ActivityRepository(Protocol):
    async def add(
        self, draft: ProspectActivityDraft, *, organization_id: UUID, actor_id: UUID, now: datetime
    ) -> ProspectActivityView: ...

    async def get(self, activity_id: UUID) -> ProspectActivityView | None: ...

    async def get_by_idempotency_key(self, prospect_id: UUID, idempotency_key: str) -> ProspectActivityView | None: ...

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[ProspectActivityView, ...]: ...


class TaskRepository(Protocol):
    async def add(
        self, draft: ProspectTaskDraft, *, organization_id: UUID, actor_id: UUID, now: datetime
    ) -> ProspectTaskView: ...

    async def get(self, task_id: UUID) -> ProspectTaskView | None: ...

    async def get_by_idempotency_key(self, prospect_id: UUID, idempotency_key: str) -> ProspectTaskView | None: ...

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[ProspectTaskView, ...]: ...

    async def list(
        self,
        *,
        limit: int,
        assigned_membership_id: UUID | None = None,
        prospect_id: UUID | None = None,
        status: str | None = None,
        due_before: datetime | None = None,
    ) -> tuple[ProspectTaskView, ...]: ...

    async def list_due_reminders(
        self, *, now: datetime, limit: int, assigned_membership_id: UUID | None = None
    ) -> tuple[ProspectTaskView, ...]: ...

    async def get_next_action(self, prospect_id: UUID) -> ProspectTaskView | None: ...

    async def list_next_actions(self, *, limit: int) -> tuple[ProspectTaskView, ...]: ...

    async def is_active_assignee(self, membership_id: UUID) -> bool: ...

    async def update(
        self,
        task_id: UUID,
        *,
        expected_version: int,
        changes: dict[str, object],
        now: datetime,
    ) -> ProspectTaskView | None: ...


class TaskEventRepository(Protocol):
    async def add(self, event: ProspectTaskEventView) -> ProspectTaskEventView: ...

    async def get_by_idempotency_key(self, task_id: UUID, idempotency_key: str) -> ProspectTaskEventView | None: ...

    async def list_for_task(self, task_id: UUID, *, limit: int) -> tuple[ProspectTaskEventView, ...]: ...

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[ProspectTaskEventView, ...]: ...
