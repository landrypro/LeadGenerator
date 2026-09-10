from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from backend.app.application.errors import TaskVersionConflict
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.activities import (
    CreateTaskUseCase,
    ListDueRemindersUseCase,
    ListNextActionsUseCase,
    ListProspectTimelineUseCase,
    UpdateTaskUseCase,
)
from backend.app.domain.activity import (
    ActivityDirection,
    ActivityType,
    ActivityValidationError,
    ContactPermissionSnapshot,
    ProspectActivityView,
    ProspectTaskDraft,
    ProspectTaskEventView,
    ProspectTaskView,
    TaskEventType,
    TaskPriority,
    TaskStatus,
)
from backend.app.domain.pipeline import ProspectStageTransitionView
from backend.app.domain.prospect import ProspectOrigin, ProspectStageCode, ProspectView


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 5, 15, tzinfo=UTC)


class MemoryTasks:
    def __init__(self) -> None:
        self.items: dict[UUID, ProspectTaskView] = {}

    async def add(
        self, draft: ProspectTaskDraft, *, organization_id: UUID, actor_id: UUID, now: datetime
    ) -> ProspectTaskView:
        result = ProspectTaskView(
            id=uuid4(),
            organization_id=organization_id,
            prospect_id=draft.prospect_id,
            created_by=actor_id,
            assigned_membership_id=draft.assigned_membership_id,
            title=draft.title,
            due_at=draft.due_at,
            priority=draft.priority,
            status=TaskStatus.OPEN,
            created_at=now,
            updated_at=now,
            version=1,
            description=draft.description,
            reminder_at=draft.reminder_at,
            reminder_acknowledged_at=None,
            reminder_snoozed_until=None,
            completed_at=None,
            cancelled_at=None,
            cancelled_reason=None,
            idempotency_key=draft.idempotency_key,
            command_fingerprint=draft.command_fingerprint,
        )
        self.items[result.id] = result
        return result

    async def get(self, task_id: UUID) -> ProspectTaskView | None:
        return self.items.get(task_id)

    async def get_by_idempotency_key(self, prospect_id: UUID, idempotency_key: str) -> ProspectTaskView | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.prospect_id == prospect_id and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def update(
        self, task_id: UUID, *, expected_version: int, changes: dict[str, object], now: datetime
    ) -> ProspectTaskView | None:
        current = self.items.get(task_id)
        if current is None or current.version != expected_version:
            return None
        updated = replace(current, **changes, updated_at=now, version=current.version + 1)
        self.items[task_id] = updated
        return updated

    async def is_active_assignee(self, membership_id: UUID) -> bool:
        return membership_id is not None

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[ProspectTaskView, ...]:
        return tuple(item for item in self.items.values() if item.prospect_id == prospect_id)[:limit]

    async def list_due_reminders(
        self, *, now: datetime, limit: int, assigned_membership_id: UUID | None = None
    ) -> tuple[ProspectTaskView, ...]:
        return tuple(
            task
            for task in self.items.values()
            if task.status is TaskStatus.OPEN
            and task.reminder_at is not None
            and task.reminder_at <= now
            and task.reminder_acknowledged_at is None
            and (task.reminder_snoozed_until is None or task.reminder_snoozed_until <= now)
            and (assigned_membership_id is None or task.assigned_membership_id == assigned_membership_id)
        )[:limit]

    async def list_next_actions(self, *, limit: int) -> tuple[ProspectTaskView, ...]:
        by_prospect: dict[UUID, ProspectTaskView] = {}
        rank = {TaskPriority.URGENT: 4, TaskPriority.HIGH: 3, TaskPriority.NORMAL: 2, TaskPriority.LOW: 1}
        for task in sorted(
            (item for item in self.items.values() if item.status is TaskStatus.OPEN),
            key=lambda item: (item.prospect_id, item.due_at, -rank[item.priority], item.id),
        ):
            by_prospect.setdefault(task.prospect_id, task)
        return tuple(by_prospect.values())[:limit]


class MemoryEvents:
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, str], ProspectTaskEventView] = {}

    async def add(self, event: ProspectTaskEventView) -> ProspectTaskEventView:
        if event.idempotency_key:
            self.items[(event.task_id, event.idempotency_key)] = event
        return event

    async def get_by_idempotency_key(self, task_id: UUID, idempotency_key: str) -> ProspectTaskEventView | None:
        return self.items.get((task_id, idempotency_key))

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[ProspectTaskEventView, ...]:
        return tuple(item for item in self.items.values() if item.prospect_id == prospect_id)[:limit]


class MemoryActivities:
    def __init__(self) -> None:
        self.items: tuple[ProspectActivityView, ...] = ()

    async def list_for_prospect(self, prospect_id: UUID, *, limit: int) -> tuple[ProspectActivityView, ...]:
        return tuple(item for item in self.items if item.prospect_id == prospect_id)[:limit]


class MemoryPipeline:
    def __init__(self) -> None:
        self.items: tuple[ProspectStageTransitionView, ...] = ()

    async def list_transitions(self, prospect_id: UUID, *, limit: int) -> tuple[ProspectStageTransitionView, ...]:
        return tuple(item for item in self.items if item.prospect_id == prospect_id)[:limit]


class MemoryAudit:
    async def record(self, event: object) -> UUID:
        return uuid4()


class MemoryProspects:
    def __init__(self, item: ProspectView) -> None:
        self.item = item

    async def get(self, prospect_id: UUID) -> ProspectView | None:
        return self.item if prospect_id == self.item.id else None


class UnitOfWork:
    def __init__(self, prospect: ProspectView) -> None:
        self.prospects = MemoryProspects(prospect)
        self.activities = MemoryActivities()
        self.tasks = MemoryTasks()
        self.task_events = MemoryEvents()
        self.pipeline = MemoryPipeline()
        self.audit = MemoryAudit()
        self.committed = False

    async def __aenter__(self) -> UnitOfWork:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        del exc_type, exc_value, traceback

    async def commit(self) -> None:
        self.committed = True


@pytest.fixture
def context() -> TenantContext:
    return TenantContext(actor_id=uuid4(), organization_id=uuid4(), request_id="activity-task-test")


@pytest.fixture
def prospect(context: TenantContext) -> ProspectView:
    now = FixedClock().now()
    return ProspectView(
        id=uuid4(),
        organization_id=context.organization_id,
        internal_alias="Atelier",
        origin=ProspectOrigin.MANUAL,
        source_label="manual",
        google_place_id=None,
        stage_code=ProspectStageCode.NEW,
        priority=0,
        version=1,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )


@pytest.mark.asyncio
async def test_timeline_includes_pipeline_transitions_and_task_events(
    context: TenantContext, prospect: ProspectView
) -> None:
    unit_of_work = UnitOfWork(prospect)
    now = FixedClock().now()
    activity = ProspectActivityView(
        id=uuid4(),
        organization_id=context.organization_id,
        prospect_id=prospect.id,
        actor_id=context.actor_id,
        activity_type=ActivityType.NOTE,
        direction=ActivityDirection.INTERNAL,
        summary="Note de suivi",
        occurred_at=now,
        created_at=now,
        note=None,
        contact_id=None,
        contact_channel_id=None,
        permission_snapshot=ContactPermissionSnapshot.NOT_APPLICABLE,
        correction_of_activity_id=None,
        correction_reason=None,
    )
    task_event = ProspectTaskEventView(
        id=uuid4(),
        organization_id=context.organization_id,
        prospect_id=prospect.id,
        task_id=uuid4(),
        actor_id=context.actor_id,
        event_type=TaskEventType.COMPLETED,
        occurred_at=now,
        resulting_status=TaskStatus.COMPLETED,
        resulting_version=2,
        changed_fields={"status": "completed"},
        reason=None,
        idempotency_key="timeline-event",
    )
    transition = ProspectStageTransitionView(
        id=uuid4(),
        prospect_id=prospect.id,
        actor_id=context.actor_id,
        from_stage=ProspectStageCode.NEW,
        to_stage=ProspectStageCode.QUALIFYING,
        from_version=1,
        resulting_version=2,
        reason_code=None,
        reason_note=None,
        occurred_at=now,
    )
    unit_of_work.activities.items = (activity,)
    unit_of_work.task_events.items[(task_event.task_id, "timeline-event")] = task_event
    unit_of_work.pipeline.items = (transition,)

    page = await ListProspectTimelineUseCase(lambda _: unit_of_work).execute(  # type: ignore[arg-type]
        context=context, prospect_id=prospect.id, limit=25, has_capability=True
    )

    assert page.activities == (activity,)
    assert page.task_events == (task_event,)
    assert page.transitions == (transition,)


@pytest.mark.asyncio
async def test_task_create_is_idempotent_and_committed(context: TenantContext, prospect: ProspectView) -> None:
    unit_of_work = UnitOfWork(prospect)
    use_case = CreateTaskUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]
    draft = ProspectTaskDraft(
        prospect_id=prospect.id,
        title="Relancer",
        due_at=FixedClock().now() + timedelta(hours=1),
        assigned_membership_id=uuid4(),
        idempotency_key="task-create-001",
        command_fingerprint="fingerprint",
    )

    first = await use_case.execute(context=context, draft=draft, has_capability=True)
    replay = await use_case.execute(context=context, draft=draft, has_capability=True)

    assert first.id == replay.id
    assert unit_of_work.committed is True


@pytest.mark.asyncio
async def test_task_update_uses_version_and_replays_before_conflict(
    context: TenantContext, prospect: ProspectView
) -> None:
    unit_of_work = UnitOfWork(prospect)
    create = CreateTaskUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]
    task = await create.execute(
        context=context,
        has_capability=True,
        draft=ProspectTaskDraft(
            prospect_id=prospect.id,
            title="Relancer",
            due_at=FixedClock().now() + timedelta(hours=1),
            assigned_membership_id=uuid4(),
            priority=TaskPriority.NORMAL,
            idempotency_key="task-create-002",
            command_fingerprint="create",
        ),
    )
    update = UpdateTaskUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    changed = await update.execute(
        context=context,
        task_id=task.id,
        expected_version=1,
        changes={"status": "completed", "completed_at": "__now__"},
        idempotency_key="task-update-001",
        can_manage=True,
        can_update_assigned=False,
        current_membership_id=None,
        action=TaskEventType.COMPLETED,
    )
    replay = await update.execute(
        context=context,
        task_id=task.id,
        expected_version=1,
        changes={"status": "completed", "completed_at": "__now__"},
        idempotency_key="task-update-001",
        can_manage=True,
        can_update_assigned=False,
        current_membership_id=None,
        action=TaskEventType.COMPLETED,
    )

    assert changed.version == 2
    assert replay.version == 2
    with pytest.raises(TaskVersionConflict):
        await update.execute(
            context=context,
            task_id=task.id,
            expected_version=1,
            changes={"title": "Retard"},
            idempotency_key="task-update-002",
            can_manage=True,
            can_update_assigned=False,
            current_membership_id=None,
        )


@pytest.mark.asyncio
async def test_due_reminder_ignores_acknowledged_and_snoozed_tasks(
    context: TenantContext, prospect: ProspectView
) -> None:
    unit_of_work = UnitOfWork(prospect)
    create = CreateTaskUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]
    task = await create.execute(
        context=context,
        has_capability=True,
        draft=ProspectTaskDraft(
            prospect_id=prospect.id,
            title="Relancer",
            due_at=FixedClock().now() + timedelta(days=1),
            reminder_at=FixedClock().now() - timedelta(minutes=1),
            assigned_membership_id=uuid4(),
            idempotency_key="task-reminder-001",
            command_fingerprint="reminder",
        ),
    )
    reminders = await ListDueRemindersUseCase(lambda _: unit_of_work, FixedClock()).execute(  # type: ignore[arg-type]
        context=context, limit=10, has_capability=True
    )

    assert [item.id for item in reminders] == [task.id]
    unit_of_work.tasks.items[task.id] = replace(task, reminder_acknowledged_at=FixedClock().now())
    acknowledged = await ListDueRemindersUseCase(lambda _: unit_of_work, FixedClock()).execute(  # type: ignore[arg-type]
        context=context, limit=10, has_capability=True
    )
    assert acknowledged == ()


@pytest.mark.asyncio
async def test_next_action_is_derived_per_prospect_and_snooze_is_bounded(
    context: TenantContext, prospect: ProspectView
) -> None:
    unit_of_work = UnitOfWork(prospect)
    create = CreateTaskUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]
    later = await create.execute(
        context=context,
        has_capability=True,
        draft=ProspectTaskDraft(
            prospect_id=prospect.id,
            title="Plus tard",
            due_at=FixedClock().now() + timedelta(days=6),
            assigned_membership_id=uuid4(),
            priority=TaskPriority.URGENT,
            idempotency_key="task-next-later",
            command_fingerprint="next-later",
        ),
    )
    sooner = await create.execute(
        context=context,
        has_capability=True,
        draft=ProspectTaskDraft(
            prospect_id=prospect.id,
            title="D’abord",
            due_at=FixedClock().now() + timedelta(days=1),
            assigned_membership_id=uuid4(),
            priority=TaskPriority.LOW,
            idempotency_key="task-next-sooner",
            command_fingerprint="next-sooner",
        ),
    )
    next_actions = await ListNextActionsUseCase(lambda _: unit_of_work).execute(  # type: ignore[arg-type]
        context=context, limit=10, has_capability=True
    )
    assert next_actions == (sooner,)

    update = UpdateTaskUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]
    with pytest.raises(ActivityValidationError, match="sept jours"):
        await update.execute(
            context=context,
            task_id=later.id,
            expected_version=later.version,
            changes={"reminder_snoozed_until": FixedClock().now() + timedelta(days=8)},
            idempotency_key="task-snooze-too-late",
            can_manage=True,
            can_update_assigned=False,
            current_membership_id=None,
            action=TaskEventType.REMINDER_SNOOZED,
        )
