from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ActivityValidationError(ValueError):
    """Une activité ou une tâche ne respecte pas son contrat métier."""


class ActivityType(StrEnum):
    NOTE = "note"
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"


class ActivityDirection(StrEnum):
    INTERNAL = "internal"
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ContactPermissionSnapshot(StrEnum):
    UNKNOWN = "unknown"
    ALLOWED = "allowed"
    RESTRICTED = "restricted"
    NOT_APPLICABLE = "not_applicable"


class TaskPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskEventType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REMINDER_ACKNOWLEDGED = "reminder_acknowledged"
    REMINDER_SNOOZED = "reminder_snoozed"
    REOPENED = "reopened"


@dataclass(frozen=True, slots=True)
class ProspectActivityDraft:
    prospect_id: UUID
    activity_type: ActivityType
    direction: ActivityDirection
    summary: str
    occurred_at: datetime
    note: str | None = None
    contact_id: UUID | None = None
    contact_channel_id: UUID | None = None
    permission_snapshot: ContactPermissionSnapshot = ContactPermissionSnapshot.NOT_APPLICABLE
    correction_of_activity_id: UUID | None = None
    correction_reason: str | None = None
    idempotency_key: str | None = None
    command_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class ProspectActivityView:
    id: UUID
    organization_id: UUID
    prospect_id: UUID
    actor_id: UUID
    activity_type: ActivityType
    direction: ActivityDirection
    summary: str
    occurred_at: datetime
    created_at: datetime
    note: str | None
    contact_id: UUID | None
    contact_channel_id: UUID | None
    permission_snapshot: ContactPermissionSnapshot
    correction_of_activity_id: UUID | None
    correction_reason: str | None
    idempotency_key: str | None = None
    command_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class ProspectTaskDraft:
    prospect_id: UUID
    title: str
    due_at: datetime
    assigned_membership_id: UUID | None = None
    description: str | None = None
    priority: TaskPriority = TaskPriority.NORMAL
    reminder_at: datetime | None = None
    idempotency_key: str | None = None
    command_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class ProspectTaskView:
    id: UUID
    organization_id: UUID
    prospect_id: UUID
    created_by: UUID
    assigned_membership_id: UUID | None
    title: str
    due_at: datetime
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    version: int
    description: str | None
    reminder_at: datetime | None
    reminder_acknowledged_at: datetime | None
    reminder_snoozed_until: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancelled_reason: str | None
    idempotency_key: str | None = None
    command_fingerprint: str | None = None
    assigned_membership_is_active: bool = True


@dataclass(frozen=True, slots=True)
class ProspectTaskEventView:
    id: UUID
    organization_id: UUID
    prospect_id: UUID
    task_id: UUID
    actor_id: UUID
    event_type: TaskEventType
    occurred_at: datetime
    resulting_status: TaskStatus
    resulting_version: int
    changed_fields: dict[str, str]
    reason: str | None
    idempotency_key: str | None = None
    command_fingerprint: str | None = None


def validate_activity_draft(draft: ProspectActivityDraft, *, now: datetime) -> ProspectActivityDraft:
    summary = _required_text(draft.summary, field="Le résumé", maximum=160)
    note = _optional_text(draft.note, field="La note", maximum=4_000)
    correction_reason = _optional_text(draft.correction_reason, field="Le motif de correction", maximum=500)
    if draft.occurred_at.tzinfo is None:
        raise ActivityValidationError("La date de l’activité doit être exprimée avec un fuseau horaire.")
    if now.tzinfo is None:
        raise ActivityValidationError("L’horloge métier doit être exprimée avec un fuseau horaire.")
    if draft.occurred_at > now:
        raise ActivityValidationError("Une activité ne peut pas être datée dans le futur.")
    if draft.activity_type in {ActivityType.CALL, ActivityType.EMAIL} and draft.direction is ActivityDirection.INTERNAL:
        raise ActivityValidationError("Un appel ou un courriel doit être déclaré entrant ou sortant.")
    if draft.activity_type is ActivityType.NOTE and draft.direction is not ActivityDirection.INTERNAL:
        raise ActivityValidationError("Une note est toujours interne.")
    if draft.correction_of_activity_id is None and correction_reason is not None:
        raise ActivityValidationError("Un motif de correction requiert une activité corrigée.")
    if draft.correction_of_activity_id is not None and correction_reason is None:
        raise ActivityValidationError("Une correction doit expliquer son motif.")
    return ProspectActivityDraft(
        prospect_id=draft.prospect_id,
        activity_type=draft.activity_type,
        direction=draft.direction,
        summary=summary,
        occurred_at=draft.occurred_at,
        note=note,
        contact_id=draft.contact_id,
        contact_channel_id=draft.contact_channel_id,
        permission_snapshot=draft.permission_snapshot,
        correction_of_activity_id=draft.correction_of_activity_id,
        correction_reason=correction_reason,
        idempotency_key=_optional_text(draft.idempotency_key, field="La clé d’idempotence", maximum=128),
        command_fingerprint=_optional_text(draft.command_fingerprint, field="L’empreinte", maximum=128),
    )


def validate_task_draft(draft: ProspectTaskDraft) -> ProspectTaskDraft:
    title = _required_text(draft.title, field="Le titre", maximum=160)
    description = _optional_text(draft.description, field="La description", maximum=2_000)
    if draft.due_at.tzinfo is None:
        raise ActivityValidationError("L’échéance doit être exprimée avec un fuseau horaire.")
    if draft.reminder_at is not None:
        if draft.reminder_at.tzinfo is None:
            raise ActivityValidationError("Le rappel doit être exprimé avec un fuseau horaire.")
        if draft.reminder_at > draft.due_at:
            raise ActivityValidationError("Le rappel ne peut pas être postérieur à l’échéance.")
    return ProspectTaskDraft(
        prospect_id=draft.prospect_id,
        title=title,
        due_at=draft.due_at,
        assigned_membership_id=draft.assigned_membership_id,
        description=description,
        priority=draft.priority,
        reminder_at=draft.reminder_at,
        idempotency_key=_optional_text(draft.idempotency_key, field="La clé d’idempotence", maximum=128),
        command_fingerprint=_optional_text(draft.command_fingerprint, field="L’empreinte", maximum=128),
    )


def _required_text(value: str, *, field: str, maximum: int) -> str:
    result = value.strip()
    if not result or len(result) > maximum:
        raise ActivityValidationError(f"{field} doit contenir entre 1 et {maximum} caractères.")
    return result


def _optional_text(value: str | None, *, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    result = value.strip()
    if not result:
        return None
    if len(result) > maximum:
        raise ActivityValidationError(f"{field} ne peut pas dépasser {maximum} caractères.")
    return result
