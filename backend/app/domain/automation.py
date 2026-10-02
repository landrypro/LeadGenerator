"""Noyau déterministe et Prévol sans effet pour l'Automatisation.

Ce module reste volontairement indépendant de la base, du worker, des connecteurs et
des fournisseurs IA. Il transforme un contexte canonique en une décision explicable
et en un Prévol immuable ; aucune fonction de ce module n'écrit dans le CRM.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from .prospect import ContactPermissionStatus


class AutomationValidationError(ValueError):
    """Le contexte ou la version d'Automatisation ne respecte pas son contrat."""


class PlaybookCode(StrEnum):
    NEW_PROSPECT = "new_prospect"
    PROPOSAL_PENDING = "proposal_pending"
    FORGOTTEN_OPPORTUNITY = "forgotten_opportunity"


class AutomationChannel(StrEnum):
    INTERNAL = "internal"
    EMAIL = "email"
    PHONE = "phone"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"


class SubjectType(StrEnum):
    PROSPECT = "prospect"
    OPPORTUNITY = "opportunity"


class FireLevel(StrEnum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    TO_VERIFY = "to_verify"


class FireReasonCode(StrEnum):
    READY = "ready"
    AUTOMATION_DISABLED = "automation_disabled"
    ORGANIZATION_INACTIVE = "organization_inactive"
    MEMBER_INACTIVE = "member_inactive"
    CAPABILITY_MISSING = "capability_missing"
    OPPOSITION_PRESENT = "opposition_present"
    PERMISSION_DENIED = "permission_denied"
    PERMISSION_UNKNOWN = "permission_unknown"
    IDENTITY_MISSING = "identity_missing"
    DATA_STALE = "data_stale"


class NextAction(StrEnum):
    REFUSE = "refuse"
    VERIFY = "verify"
    PREPARE = "prepare"


AUTOMATION_PREPARE_CAPABILITY: Final = "automation:prepare:self"
DEFAULT_PREFLIGHT_TTL: Final = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class AutomationFeatureFlags:
    """Les trois verrous exigés avant toute admission Automation.

    Les valeurs par défaut sont volontairement fermées.  Cette structure ne
    réalise aucune persistance : les valeurs organisation et Playbook seront
    chargées depuis les tables dédiées lorsqu'une tranche ultérieure ajoutera
    les cas d'usage correspondants.
    """

    global_enabled: bool = False
    organization_enabled: bool = False
    playbook_enabled: bool = False

    @property
    def preparation_enabled(self) -> bool:
        return self.global_enabled and self.organization_enabled and self.playbook_enabled

    @property
    def disabled_scope(self) -> str | None:
        if not self.global_enabled:
            return "global"
        if not self.organization_enabled:
            return "organization"
        if not self.playbook_enabled:
            return "playbook"
        return None


def _ensure_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AutomationValidationError(f"{field_name} doit être une date avec fuseau horaire.")


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class PlaybookVersion:
    """Version immuable d'un Playbook utilisable par un Prévol."""

    playbook_id: str
    code: PlaybookCode
    version: int
    ruleset_version: str
    active: bool = True

    def __post_init__(self) -> None:
        if not self.playbook_id.strip():
            raise AutomationValidationError("L'identifiant du Playbook est obligatoire.")
        if self.version < 1:
            raise AutomationValidationError("La version du Playbook doit être positive.")
        if not self.ruleset_version.strip():
            raise AutomationValidationError("La version des règles est obligatoire.")

    @property
    def snapshot_fingerprint(self) -> str:
        return _fingerprint(
            {
                "playbook_id": self.playbook_id,
                "code": self.code.value,
                "version": self.version,
                "ruleset_version": self.ruleset_version,
                "active": self.active,
            }
        )


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    """Entrée fermée et canonique du moteur déterministe."""

    organization_id: UUID
    actor_id: UUID
    actor_membership_id: UUID
    role: str
    capabilities: frozenset[str]
    subject_type: SubjectType
    subject_id: UUID
    playbook: PlaybookVersion
    channel: AutomationChannel
    permission: ContactPermissionStatus
    organization_active: bool
    member_active: bool
    global_enabled: bool
    organization_enabled: bool
    playbook_enabled: bool
    identity_present: bool
    data_fresh: bool
    opposition_present: bool
    crm_version: int
    suspension_generation: int
    evaluated_at: datetime

    def __post_init__(self) -> None:
        _ensure_aware(self.evaluated_at, field_name="evaluated_at")
        if not self.role.strip():
            raise AutomationValidationError("Le rôle de l'acteur est obligatoire.")
        if self.crm_version < 0:
            raise AutomationValidationError("La version CRM ne peut pas être négative.")
        if self.suspension_generation < 0:
            raise AutomationValidationError("La génération de suspension ne peut pas être négative.")

    @property
    def snapshot_fingerprint(self) -> str:
        """Empreinte des entrées qui doivent rester identiques entre Prévol et effet futur."""

        return _fingerprint(
            {
                "organization_id": str(self.organization_id),
                "actor_id": str(self.actor_id),
                "actor_membership_id": str(self.actor_membership_id),
                "role": self.role,
                "capabilities": sorted(self.capabilities),
                "subject_type": self.subject_type.value,
                "subject_id": str(self.subject_id),
                "playbook_snapshot": self.playbook.snapshot_fingerprint,
                "channel": self.channel.value,
                "permission": self.permission.value,
                "organization_active": self.organization_active,
                "member_active": self.member_active,
                "global_enabled": self.global_enabled,
                "organization_enabled": self.organization_enabled,
                "playbook_enabled": self.playbook_enabled,
                "identity_present": self.identity_present,
                "data_fresh": self.data_fresh,
                "opposition_present": self.opposition_present,
                "crm_version": self.crm_version,
                "suspension_generation": self.suspension_generation,
            }
        )


@dataclass(frozen=True, slots=True)
class FireDecision:
    level: FireLevel
    reason_codes: tuple[FireReasonCode, ...]
    next_action: NextAction
    blocking_fields: tuple[str, ...]
    ruleset_version: str
    evaluated_at: datetime

    def __post_init__(self) -> None:
        _ensure_aware(self.evaluated_at, field_name="evaluated_at")
        if not self.reason_codes:
            raise AutomationValidationError("Une décision Feu doit avoir au moins un motif.")


@dataclass(frozen=True, slots=True)
class PreflightAction:
    """Action proposée à titre informatif ; elle n'est jamais créée par le Prévol."""

    kind: NextAction
    subject_id: UUID
    effect_allowed: bool = False


@dataclass(frozen=True, slots=True)
class PreflightPlan:
    """Prévol immuable, expirant et explicitement sans effet."""

    organization_id: UUID
    subject_id: UUID
    playbook_snapshot_fingerprint: str
    context_snapshot_fingerprint: str
    decision: FireDecision
    proposed_actions: tuple[PreflightAction, ...]
    created_at: datetime
    expires_at: datetime
    effect_free: bool = True
    crm_mutation_count: int = 0

    def __post_init__(self) -> None:
        _ensure_aware(self.created_at, field_name="created_at")
        _ensure_aware(self.expires_at, field_name="expires_at")
        if self.expires_at <= self.created_at:
            raise AutomationValidationError("Un Prévol doit expirer après sa création.")
        if not self.effect_free or self.crm_mutation_count != 0:
            raise AutomationValidationError("Un Prévol doit rester sans effet CRM.")
        if any(action.effect_allowed for action in self.proposed_actions):
            raise AutomationValidationError("Une action de Prévol ne peut pas autoriser un effet.")

    @property
    def plan_fingerprint(self) -> str:
        return _fingerprint(
            {
                "organization_id": str(self.organization_id),
                "subject_id": str(self.subject_id),
                "playbook_snapshot": self.playbook_snapshot_fingerprint,
                "context_snapshot": self.context_snapshot_fingerprint,
                "level": self.decision.level.value,
                "reasons": [reason.value for reason in self.decision.reason_codes],
                "next_action": self.decision.next_action.value,
                "created_at": self.created_at.isoformat(),
                "expires_at": self.expires_at.isoformat(),
            }
        )

    def is_current(self, context: EvaluationContext, *, at: datetime) -> bool:
        _ensure_aware(at, field_name="at")
        return (
            at < self.expires_at
            and context.organization_id == self.organization_id
            and context.subject_id == self.subject_id
            and context.playbook.snapshot_fingerprint == self.playbook_snapshot_fingerprint
            and context.snapshot_fingerprint == self.context_snapshot_fingerprint
        )


class DeterministicAutomationEngine:
    """Évalue le Feu et construit un Prévol sans effet métier."""

    def evaluate(self, context: EvaluationContext) -> FireDecision:
        red_reasons: list[FireReasonCode] = []
        yellow_reasons: list[FireReasonCode] = []
        uncertain_reasons: list[FireReasonCode] = []
        blocking_fields: list[str] = []

        if not context.organization_active:
            red_reasons.append(FireReasonCode.ORGANIZATION_INACTIVE)
            blocking_fields.append("organization_active")
        if not (context.global_enabled and context.organization_enabled and context.playbook_enabled):
            red_reasons.append(FireReasonCode.AUTOMATION_DISABLED)
            blocking_fields.append("automation_flags")
        if not context.member_active:
            red_reasons.append(FireReasonCode.MEMBER_INACTIVE)
            blocking_fields.append("member_active")
        if AUTOMATION_PREPARE_CAPABILITY not in context.capabilities:
            red_reasons.append(FireReasonCode.CAPABILITY_MISSING)
            blocking_fields.append("capabilities")
        if context.opposition_present:
            red_reasons.append(FireReasonCode.OPPOSITION_PRESENT)
            blocking_fields.append("opposition_present")
        if context.permission in {
            ContactPermissionStatus.DO_NOT_CONTACT,
            ContactPermissionStatus.OPTED_OUT,
        }:
            red_reasons.append(FireReasonCode.PERMISSION_DENIED)
            blocking_fields.append("permission")

        if context.permission is ContactPermissionStatus.UNKNOWN:
            yellow_reasons.append(FireReasonCode.PERMISSION_UNKNOWN)
            blocking_fields.append("permission")
        if not context.identity_present:
            uncertain_reasons.append(FireReasonCode.IDENTITY_MISSING)
            blocking_fields.append("identity_present")
        if not context.data_fresh:
            uncertain_reasons.append(FireReasonCode.DATA_STALE)
            blocking_fields.append("data_fresh")

        if red_reasons:
            return FireDecision(
                level=FireLevel.RED,
                reason_codes=tuple(red_reasons),
                next_action=NextAction.REFUSE,
                blocking_fields=tuple(blocking_fields),
                ruleset_version=context.playbook.ruleset_version,
                evaluated_at=context.evaluated_at,
            )
        if uncertain_reasons:
            return FireDecision(
                level=FireLevel.TO_VERIFY,
                reason_codes=tuple(uncertain_reasons),
                next_action=NextAction.VERIFY,
                blocking_fields=tuple(blocking_fields),
                ruleset_version=context.playbook.ruleset_version,
                evaluated_at=context.evaluated_at,
            )
        if yellow_reasons:
            return FireDecision(
                level=FireLevel.YELLOW,
                reason_codes=tuple(yellow_reasons),
                next_action=NextAction.VERIFY,
                blocking_fields=tuple(blocking_fields),
                ruleset_version=context.playbook.ruleset_version,
                evaluated_at=context.evaluated_at,
            )
        return FireDecision(
            level=FireLevel.GREEN,
            reason_codes=(FireReasonCode.READY,),
            next_action=NextAction.PREPARE,
            blocking_fields=(),
            ruleset_version=context.playbook.ruleset_version,
            evaluated_at=context.evaluated_at,
        )

    def prepare(
        self,
        context: EvaluationContext,
        *,
        ttl: timedelta = DEFAULT_PREFLIGHT_TTL,
    ) -> PreflightPlan:
        if ttl <= timedelta(0):
            raise AutomationValidationError("La durée de vie du Prévol doit être positive.")
        decision = self.evaluate(context)
        return PreflightPlan(
            organization_id=context.organization_id,
            subject_id=context.subject_id,
            playbook_snapshot_fingerprint=context.playbook.snapshot_fingerprint,
            context_snapshot_fingerprint=context.snapshot_fingerprint,
            decision=decision,
            proposed_actions=(PreflightAction(kind=decision.next_action, subject_id=context.subject_id),),
            created_at=context.evaluated_at,
            expires_at=context.evaluated_at + ttl,
        )
