from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from ...domain.activity import (
    ActivityValidationError,
    ContactPermissionSnapshot,
    ProspectActivityDraft,
    ProspectActivityView,
    ProspectTaskDraft,
    ProspectTaskEventView,
    ProspectTaskView,
    TaskEventType,
    TaskPriority,
    TaskStatus,
    validate_activity_draft,
    validate_task_draft,
)
from ...domain.audit import AuditAction
from ...domain.pipeline import ProspectStageTransitionView
from ...domain.prospect import ContactPermissionStatus
from ..audit_events import tenant_audit_event
from ..errors import (
    ActivityResourceNotFound,
    IdempotencyKeyReused,
    InsufficientCapability,
    ProspectArchivedReadOnly,
    ProspectResourceNotFound,
    TaskResourceNotFound,
    TaskVersionConflict,
)
from ..ports.clock import Clock
from ..ports.metrics import CrmTaskAction, MetricsRecorder, NullMetricsRecorder
from ..ports.prospect import ProspectUnitOfWork, ProspectUnitOfWorkFactory
from ..tenancy import TenantContext


@dataclass(frozen=True, slots=True)
class TimelinePage:
    activities: tuple[ProspectActivityView, ...]
    tasks: tuple[ProspectTaskView, ...]
    task_events: tuple[ProspectTaskEventView, ...]
    transitions: tuple[ProspectStageTransitionView, ...]


class CreateActivityUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock, metrics: MetricsRecorder | None = None
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(
        self, *, context: TenantContext, draft: ProspectActivityDraft, has_capability: bool
    ) -> ProspectActivityView:
        _require(has_capability)
        now = self._clock.now()
        try:
            draft = validate_activity_draft(draft, now=now)
            async with self._unit_of_work_factory(context) as unit_of_work:
                prospect = await unit_of_work.prospects.get(draft.prospect_id)
                _require_writable_prospect(prospect)
                draft = await _bind_activity_channel(unit_of_work, draft)
                if draft.idempotency_key:
                    replay = await unit_of_work.activities.get_by_idempotency_key(
                        draft.prospect_id, draft.idempotency_key
                    )
                    if replay:
                        if replay.command_fingerprint != draft.command_fingerprint:
                            raise IdempotencyKeyReused
                        return replay
                activity = await unit_of_work.activities.add(
                    draft, organization_id=context.organization_id, actor_id=context.actor_id, now=now
                )
                action = (
                    AuditAction.PROSPECT_ACTIVITY_CORRECTED
                    if draft.correction_of_activity_id
                    else AuditAction.PROSPECT_ACTIVITY_CREATED
                )
                await unit_of_work.audit.record(
                    tenant_audit_event(
                        context,
                        action,
                        activity.id,
                        {
                            "activity_type": activity.activity_type.value,
                            "direction": activity.direction.value,
                            "correction": bool(draft.correction_of_activity_id),
                        },
                    )
                )
                await unit_of_work.commit()
                self._metrics.record_crm_activity_command(activity.activity_type.value, "accepted")
                return activity
        except Exception:
            self._metrics.record_crm_activity_command(draft.activity_type.value, "rejected")
            raise

    async def correct(
        self,
        *,
        context: TenantContext,
        activity_id: UUID,
        summary: str,
        note: str | None,
        occurred_at: datetime,
        correction_reason: str,
        idempotency_key: str,
        can_correct_any: bool,
        can_correct_self: bool,
    ) -> ProspectActivityView:
        async with self._unit_of_work_factory(context) as unit_of_work:
            original = await unit_of_work.activities.get(activity_id)
        if original is None:
            raise ActivityResourceNotFound
        if not can_correct_any and not (can_correct_self and original.actor_id == context.actor_id):
            raise InsufficientCapability
        draft = ProspectActivityDraft(
            prospect_id=original.prospect_id,
            activity_type=original.activity_type,
            direction=original.direction,
            summary=summary,
            note=note,
            occurred_at=occurred_at,
            contact_id=original.contact_id,
            contact_channel_id=original.contact_channel_id,
            permission_snapshot=original.permission_snapshot,
            correction_of_activity_id=activity_id,
            correction_reason=correction_reason,
            idempotency_key=idempotency_key,
            command_fingerprint=_fingerprint(activity_id, summary, note, occurred_at, correction_reason),
        )
        return await self.execute(context=context, draft=draft, has_capability=True)


class CreateTaskUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock, metrics: MetricsRecorder | None = None
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(
        self, *, context: TenantContext, draft: ProspectTaskDraft, has_capability: bool
    ) -> ProspectTaskView:
        _require(has_capability)
        now = self._clock.now()
        try:
            draft = validate_task_draft(draft)
            if draft.due_at <= now:
                raise ActivityValidationError("L’échéance d’une nouvelle tâche doit être dans le futur.")
            async with self._unit_of_work_factory(context) as unit_of_work:
                prospect = await unit_of_work.prospects.get(draft.prospect_id)
                _require_writable_prospect(prospect)
                if draft.assigned_membership_id is None or not await unit_of_work.tasks.is_active_assignee(
                    draft.assigned_membership_id
                ):
                    raise ActivityValidationError("Le responsable de la tâche doit être un membre actif.")
                if draft.idempotency_key:
                    replay = await unit_of_work.tasks.get_by_idempotency_key(draft.prospect_id, draft.idempotency_key)
                    if replay:
                        if replay.command_fingerprint != draft.command_fingerprint:
                            raise IdempotencyKeyReused
                        return replay
                task = await unit_of_work.tasks.add(
                    draft, organization_id=context.organization_id, actor_id=context.actor_id, now=now
                )
                await unit_of_work.task_events.add(
                    _task_event(
                        task,
                        context,
                        TaskEventType.CREATED,
                        now,
                        {"title": "changed"},
                        None,
                        draft.idempotency_key,
                        draft.command_fingerprint,
                    )
                )
                await unit_of_work.audit.record(
                    tenant_audit_event(
                        context,
                        AuditAction.PROSPECT_TASK_CREATED,
                        task.id,
                        {"resulting_status": task.status.value, "resulting_version": task.version},
                    )
                )
                await unit_of_work.commit()
                self._metrics.record_crm_task_command("created", "accepted")
                return task
        except Exception:
            self._metrics.record_crm_task_command("created", "rejected")
            raise


class UpdateTaskUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock, metrics: MetricsRecorder | None = None
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(
        self,
        *,
        context: TenantContext,
        task_id: UUID,
        expected_version: int,
        changes: dict[str, object],
        idempotency_key: str,
        can_manage: bool,
        can_update_assigned: bool,
        current_membership_id: UUID | None,
        action: TaskEventType = TaskEventType.UPDATED,
        reason: str | None = None,
    ) -> ProspectTaskView:
        now = self._clock.now()
        action_name = _action_name(action)
        changes = {name: (now if value == "__now__" else value) for name, value in changes.items()}
        if not changes:
            raise ActivityValidationError("La modification de tâche ne contient aucun champ.")
        if action is TaskEventType.REMINDER_SNOOZED and changes.get("reminder_snoozed_until") is None:
            raise ActivityValidationError("Un report de rappel requiert une nouvelle échéance.")
        if isinstance(changes.get("status"), str):
            changes["status"] = TaskStatus(str(changes["status"]))
        if isinstance(changes.get("priority"), str):
            changes["priority"] = TaskPriority(str(changes["priority"]))
        fingerprint = _fingerprint(task_id, expected_version, action.value, changes, reason)
        try:
            async with self._unit_of_work_factory(context) as unit_of_work:
                task = await unit_of_work.tasks.get(task_id)
                if task is None:
                    raise TaskResourceNotFound
                if not can_manage and not (
                    can_update_assigned
                    and current_membership_id is not None
                    and task.assigned_membership_id == current_membership_id
                ):
                    raise InsufficientCapability
                replay = await unit_of_work.task_events.get_by_idempotency_key(task_id, idempotency_key)
                if replay:
                    if replay.command_fingerprint != fingerprint:
                        raise IdempotencyKeyReused
                    return task
                if task.version != expected_version:
                    self._metrics.record_crm_task_version_conflict()
                    raise TaskVersionConflict(task.version)
                _validate_task_changes(task, changes, now=now, action=action, reason=reason)
                assignee = changes.get("assigned_membership_id")
                if assignee is not None and not await unit_of_work.tasks.is_active_assignee(cast(UUID, assignee)):
                    raise ActivityValidationError("Le responsable de la tâche doit être un membre actif.")
                _ensure_task_action_allowed(task.status, action)
                updated = await unit_of_work.tasks.update(
                    task_id, expected_version=expected_version, changes=changes, now=now
                )
                if updated is None:
                    self._metrics.record_crm_task_version_conflict()
                    raise TaskVersionConflict(task.version)
                await unit_of_work.task_events.add(
                    _task_event(
                        updated,
                        context,
                        action,
                        now,
                        {name: "changed" for name in changes},
                        reason,
                        idempotency_key,
                        fingerprint,
                    )
                )
                await unit_of_work.audit.record(
                    tenant_audit_event(
                        context,
                        _audit_action(action),
                        updated.id,
                        {
                            "resulting_status": updated.status.value,
                            "resulting_version": updated.version,
                            "changed_fields": list(changes),
                        },
                    )
                )
                await unit_of_work.commit()
                self._metrics.record_crm_task_command(action_name, "accepted")
                return updated
        except Exception:
            self._metrics.record_crm_task_command(action_name, "rejected")
            raise


class ListProspectTimelineUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, metrics: MetricsRecorder | None = None) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(
        self, *, context: TenantContext, prospect_id: UUID, limit: int, has_capability: bool
    ) -> TimelinePage:
        _require(has_capability)
        if not 1 <= limit <= 100:
            raise ValueError("La limite de chronologie est invalide.")
        try:
            async with self._unit_of_work_factory(context) as unit_of_work:
                if await unit_of_work.prospects.get(prospect_id) is None:
                    raise ProspectResourceNotFound
                result = TimelinePage(
                    activities=await unit_of_work.activities.list_for_prospect(prospect_id, limit=limit),
                    tasks=await unit_of_work.tasks.list_for_prospect(prospect_id, limit=limit),
                    task_events=await unit_of_work.task_events.list_for_prospect(prospect_id, limit=limit),
                    transitions=await unit_of_work.pipeline.list_transitions(prospect_id, limit=limit),
                )
            self._metrics.record_crm_timeline_request("accepted")
            return result
        except Exception:
            self._metrics.record_crm_timeline_request("rejected")
            raise


class ListTasksUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        limit: int,
        has_capability: bool,
        assigned_membership_id: UUID | None = None,
        prospect_id: UUID | None = None,
        status: str | None = None,
        due_before: datetime | None = None,
    ) -> tuple[ProspectTaskView, ...]:
        _require(has_capability)
        if not 1 <= limit <= 100:
            raise ValueError("La limite des tâches est invalide.")
        async with self._unit_of_work_factory(context) as unit_of_work:
            return await unit_of_work.tasks.list(
                limit=limit,
                assigned_membership_id=assigned_membership_id,
                prospect_id=prospect_id,
                status=status,
                due_before=due_before,
            )


class ListDueRemindersUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        limit: int,
        has_capability: bool,
        assigned_membership_id: UUID | None = None,
    ) -> tuple[ProspectTaskView, ...]:
        _require(has_capability)
        if not 1 <= limit <= 100:
            raise ValueError("La limite des rappels est invalide.")
        async with self._unit_of_work_factory(context) as unit_of_work:
            return await unit_of_work.tasks.list_due_reminders(
                now=self._clock.now(), limit=limit, assigned_membership_id=assigned_membership_id
            )


class ListNextActionsUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self, *, context: TenantContext, limit: int, has_capability: bool
    ) -> tuple[ProspectTaskView, ...]:
        _require(has_capability)
        if not 1 <= limit <= 500:
            raise ValueError("La limite des prochaines actions est invalide.")
        async with self._unit_of_work_factory(context) as unit_of_work:
            return await unit_of_work.tasks.list_next_actions(limit=limit)


def _require(has_capability: bool) -> None:
    if not has_capability:
        raise InsufficientCapability


def _require_writable_prospect(prospect: object | None) -> None:
    if prospect is None:
        raise ProspectResourceNotFound
    if getattr(prospect, "archived_at", None) is not None:
        raise ProspectArchivedReadOnly


async def _bind_activity_channel(
    unit_of_work: ProspectUnitOfWork, draft: ProspectActivityDraft
) -> ProspectActivityDraft:
    """Lie une activité déclarative à un canal du prospect et fige sa permission.

    Cette étape n'envoie rien : elle vérifie seulement que le canal appartient bien
    au prospect avant de conserver l'état de permission observé au moment du suivi.
    """
    if draft.contact_channel_id is None:
        return draft

    channel = await unit_of_work.contact_channels.get(draft.contact_channel_id)
    if channel is None:
        raise ActivityValidationError("Le canal associé à l’activité est introuvable.")
    contact_id = channel.contact_id
    belongs_to_prospect = channel.prospect_id == draft.prospect_id
    if not belongs_to_prospect and contact_id is not None:
        contact = await unit_of_work.contacts.get(contact_id)
        belongs_to_prospect = contact is not None and contact.prospect_id == draft.prospect_id
    if not belongs_to_prospect:
        raise ActivityValidationError("Le canal associé n’appartient pas à ce prospect.")

    permission = await unit_of_work.contact_permissions.get_by_channel(channel.id)
    snapshot = {
        ContactPermissionStatus.ALLOWED: ContactPermissionSnapshot.ALLOWED,
        ContactPermissionStatus.UNKNOWN: ContactPermissionSnapshot.UNKNOWN,
        ContactPermissionStatus.DO_NOT_CONTACT: ContactPermissionSnapshot.RESTRICTED,
        ContactPermissionStatus.OPTED_OUT: ContactPermissionSnapshot.RESTRICTED,
    }.get(permission.status if permission else ContactPermissionStatus.UNKNOWN, ContactPermissionSnapshot.UNKNOWN)
    return replace(draft, contact_id=contact_id, permission_snapshot=snapshot)


def _fingerprint(*values: object) -> str:
    return hashlib.sha256(
        json.dumps(values, default=str, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _task_event(
    task: ProspectTaskView,
    context: TenantContext,
    event_type: TaskEventType,
    now: datetime,
    changed_fields: dict[str, str],
    reason: str | None,
    idempotency_key: str | None,
    command_fingerprint: str | None,
) -> ProspectTaskEventView:
    return ProspectTaskEventView(
        id=uuid4(),
        organization_id=context.organization_id,
        prospect_id=task.prospect_id,
        task_id=task.id,
        actor_id=context.actor_id,
        event_type=event_type,
        occurred_at=now,
        resulting_status=task.status,
        resulting_version=task.version,
        changed_fields=changed_fields,
        reason=reason,
        idempotency_key=idempotency_key,
        command_fingerprint=command_fingerprint,
    )


def _action_name(event_type: TaskEventType) -> CrmTaskAction:
    return cast(
        CrmTaskAction,
        {
            TaskEventType.CREATED: "created",
            TaskEventType.COMPLETED: "completed",
            TaskEventType.CANCELLED: "cancelled",
            TaskEventType.REOPENED: "reopened",
            TaskEventType.REMINDER_ACKNOWLEDGED: "reminder_changed",
            TaskEventType.REMINDER_SNOOZED: "reminder_changed",
        }.get(event_type, "updated"),
    )


def _audit_action(event_type: TaskEventType) -> AuditAction:
    return {
        TaskEventType.COMPLETED: AuditAction.PROSPECT_TASK_COMPLETED,
        TaskEventType.CANCELLED: AuditAction.PROSPECT_TASK_CANCELLED,
        TaskEventType.REOPENED: AuditAction.PROSPECT_TASK_REOPENED,
        TaskEventType.REMINDER_ACKNOWLEDGED: AuditAction.PROSPECT_TASK_REMINDER_CHANGED,
        TaskEventType.REMINDER_SNOOZED: AuditAction.PROSPECT_TASK_REMINDER_CHANGED,
    }.get(event_type, AuditAction.PROSPECT_TASK_UPDATED)


def _ensure_task_action_allowed(status: TaskStatus, event_type: TaskEventType) -> None:
    if event_type in {TaskEventType.COMPLETED, TaskEventType.CANCELLED} and status is not TaskStatus.OPEN:
        raise ActivityValidationError("Seule une tâche ouverte peut être finalisée.")
    if event_type is TaskEventType.REOPENED and status is TaskStatus.OPEN:
        raise ActivityValidationError("La tâche est déjà ouverte.")
    if (
        event_type in {TaskEventType.REMINDER_ACKNOWLEDGED, TaskEventType.REMINDER_SNOOZED}
        and status is not TaskStatus.OPEN
    ):
        raise ActivityValidationError("Le rappel d’une tâche fermée ne peut pas être modifié.")


def _validate_task_changes(
    task: ProspectTaskView, changes: dict[str, object], *, now: datetime, action: TaskEventType, reason: str | None
) -> None:
    due_at = cast(datetime, changes.get("due_at", task.due_at))
    reminder_at = cast(datetime | None, changes.get("reminder_at", task.reminder_at))
    if action is TaskEventType.UPDATED or "due_at" in changes or "reminder_at" in changes:
        if due_at.tzinfo is None or due_at <= now:
            raise ActivityValidationError("L’échéance doit être exprimée dans le futur avec un fuseau horaire.")
        if reminder_at is not None and (reminder_at.tzinfo is None or reminder_at > due_at):
            raise ActivityValidationError("Le rappel doit être daté et ne peut pas dépasser l’échéance.")
    if action is TaskEventType.REMINDER_SNOOZED:
        snoozed_until = cast(datetime | None, changes.get("reminder_snoozed_until"))
        if snoozed_until is None or snoozed_until.tzinfo is None or snoozed_until <= now:
            raise ActivityValidationError("Le report de rappel doit être dans le futur.")
        if snoozed_until > now + timedelta(days=7):
            raise ActivityValidationError("Le report de rappel ne peut pas dépasser sept jours.")
    if action in {TaskEventType.CANCELLED, TaskEventType.REOPENED} and not (reason or "").strip():
        raise ActivityValidationError("Cette action de tâche requiert un motif.")
