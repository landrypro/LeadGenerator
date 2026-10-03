"""Contrat déterministe de l'admission IMP-A3, sans accès à l'infrastructure.

Une admission ne prépare pas elle-même une tâche CRM.  Elle décrit le travail
durable à faire après validation du Prévol, puis le futur exécuteur contrôlé
rejouera les gardes avant la moindre écriture.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from .activity import ProspectTaskDraft, TaskPriority
from .automation import AutomationFeatureFlags, AutomationValidationError

AUTOMATION_NEW_PROSPECT_JOB_TYPE = "automation_new_prospect_prepare"
AUTOMATION_NEW_PROSPECT_JOB_SCHEMA_VERSION = 1
INTERNAL_TASK_DESCRIPTION = "Vérifier le contexte disponible et définir la prochaine action."
INTERNAL_TASK_DUE_DELAY = timedelta(hours=24)


class AutomationAdmissionState(StrEnum):
    ACCEPTED = "accepted"
    PREFLIGHT_REQUIRED = "preflight_required"
    READY_TO_PREPARE = "ready_to_prepare"
    PREPARED = "prepared"
    BLOCKED = "blocked"
    QUARANTINED = "quarantined"
    TO_VERIFY = "to_verify"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AutomationAdmissionValidationError(AutomationValidationError):
    """Une admission ou sa double garde n'autorise pas de préparation."""


def _ensure_aware(value: datetime, *, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AutomationAdmissionValidationError(f"{field} doit contenir un fuseau horaire.")


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class NewProspectAdmission:
    """Données persistables, sans stocker la clé d'idempotence en clair."""

    organization_id: UUID
    prospect_id: UUID
    playbook_version_id: UUID
    requested_by_membership_id: UUID
    preflight_id: UUID
    decision_id: UUID
    correlation_id: UUID
    functional_identity: str
    idempotency_key: str
    admitted_at: datetime

    def __post_init__(self) -> None:
        if not self.functional_identity.strip():
            raise AutomationAdmissionValidationError("L'identité fonctionnelle est obligatoire.")
        if not self.idempotency_key.strip() or len(self.idempotency_key) > 128:
            raise AutomationAdmissionValidationError(
                "La clé d'idempotence est obligatoire et limitée à 128 caractères."
            )
        _ensure_aware(self.admitted_at, field="La date d'admission")

    @property
    def functional_identity_fingerprint(self) -> str:
        return _digest(
            {
                "organization_id": str(self.organization_id),
                "prospect_id": str(self.prospect_id),
                "playbook_version_id": str(self.playbook_version_id),
                "functional_identity": self.functional_identity.strip(),
            }
        )

    @property
    def idempotency_key_digest(self) -> str:
        return hashlib.sha256(self.idempotency_key.encode("utf-8")).hexdigest()

    @property
    def request_fingerprint(self) -> str:
        return _digest(
            {
                "organization_id": str(self.organization_id),
                "prospect_id": str(self.prospect_id),
                "playbook_version_id": str(self.playbook_version_id),
                "requested_by_membership_id": str(self.requested_by_membership_id),
                "preflight_id": str(self.preflight_id),
                "decision_id": str(self.decision_id),
                "functional_identity_fingerprint": self.functional_identity_fingerprint,
                "job_type": AUTOMATION_NEW_PROSPECT_JOB_TYPE,
                "job_schema_version": AUTOMATION_NEW_PROSPECT_JOB_SCHEMA_VERSION,
            }
        )


@dataclass(frozen=True, slots=True)
class PreparationGuard:
    """Snapshot relu par l'exécuteur avant l'effet CRM, jamais réutilisé à l'aveugle."""

    feature_flags: AutomationFeatureFlags
    preflight_is_current: bool
    decision_is_prepare: bool
    prospect_is_writable: bool
    assigned_membership_id: UUID | None
    assigned_membership_is_active: bool

    @property
    def blocking_code(self) -> str | None:
        if not self.feature_flags.preparation_enabled:
            return "automation_disabled"
        if not self.preflight_is_current:
            return "preflight_stale"
        if not self.decision_is_prepare:
            return "decision_not_preparable"
        if not self.prospect_is_writable:
            return "prospect_not_writable"
        if self.assigned_membership_id is None or not self.assigned_membership_is_active:
            return "owner_unavailable"
        return None

    def require_preparable(self) -> UUID:
        if self.blocking_code is not None:
            raise AutomationAdmissionValidationError(f"Préparation bloquée : {self.blocking_code}.")
        assert self.assigned_membership_id is not None
        return self.assigned_membership_id


def build_internal_task_draft(
    admission: NewProspectAdmission,
    *,
    prospect_display_name: str,
    guard: PreparationGuard,
) -> ProspectTaskDraft:
    """Construit la seule tâche IMP-A3 après le second contrôle des gardes."""

    assigned_membership_id = guard.require_preparable()
    display_name = prospect_display_name.strip()
    if not display_name:
        raise AutomationAdmissionValidationError("Le nom d'affichage du prospect est obligatoire.")
    if len(display_name) > 122:
        raise AutomationAdmissionValidationError("Le nom d'affichage du prospect est trop long pour le titre de tâche.")
    task_key = f"automation-admission:{admission.idempotency_key_digest}"
    return ProspectTaskDraft(
        prospect_id=admission.prospect_id,
        title=f"Prendre en charge le prospect {display_name}",
        description=INTERNAL_TASK_DESCRIPTION,
        due_at=admission.admitted_at + INTERNAL_TASK_DUE_DELAY,
        assigned_membership_id=assigned_membership_id,
        priority=TaskPriority.NORMAL,
        idempotency_key=task_key,
        command_fingerprint=_digest(
            {
                "admission_request": admission.request_fingerprint,
                "assigned_membership_id": str(assigned_membership_id),
                "title": f"Prendre en charge le prospect {display_name}",
                "due_at": (admission.admitted_at + INTERNAL_TASK_DUE_DELAY).isoformat(),
            }
        ),
    )
