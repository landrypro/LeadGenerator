"""Contrat fermé de l'Assistant IMP-A5, sans outil ni effet métier."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class AssistantValidationError(ValueError):
    """La sortie de l'interpréteur ne respecte pas le schéma fermé."""


class AssistantIntentCode(StrEnum):
    SCOPE_OPEN_PROSPECTS = "scope_open_prospects"
    REBALANCE_OPEN_PROSPECTS = "rebalance_open_prospects"
    PREPARE_NEW_PROSPECT_FOLLOWUP = "prepare_new_prospect_followup"
    REVIEW_PENDING_PROPOSALS = "review_pending_proposals"
    REVIEW_FORGOTTEN_OPPORTUNITIES = "review_forgotten_opportunities"
    EXPLAIN_AUTOMATION_STATUS = "explain_automation_status"
    CLARIFY_REQUEST = "clarify_request"
    UNSUPPORTED_REQUEST = "unsupported_request"


class AssistantScopeKind(StrEnum):
    ASSIGNED_OPEN_PROSPECTS = "assigned_open_prospects"
    ORGANIZATION_OPEN_PROSPECTS = "organization_open_prospects"
    NEW_PROSPECTS = "new_prospects"
    AUTOMATION_STATUS = "automation_status"
    NONE = "none"


class AssistantResultCode(StrEnum):
    PLAN_READY = "plan_ready"
    CLARIFICATION_REQUIRED = "clarification_required"
    INTENT_NOT_SUPPORTED = "intent_not_supported"
    FALLBACK_GUIDED = "fallback_guided"


class AssistantFallbackReason(StrEnum):
    TIMEOUT = "timeout"
    QUOTA_BLOCKED = "quota_blocked"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INTENT_OUTPUT_INVALID = "intent_output_invalid"


ACTIVE_ASSISTANT_INTENTS: Final = (
    AssistantIntentCode.SCOPE_OPEN_PROSPECTS,
    AssistantIntentCode.REBALANCE_OPEN_PROSPECTS,
    AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP,
    AssistantIntentCode.EXPLAIN_AUTOMATION_STATUS,
    AssistantIntentCode.CLARIFY_REQUEST,
    AssistantIntentCode.UNSUPPORTED_REQUEST,
)
GUIDED_ASSISTANT_INTENTS: Final = (
    AssistantIntentCode.SCOPE_OPEN_PROSPECTS,
    AssistantIntentCode.REBALANCE_OPEN_PROSPECTS,
    AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP,
)
ASSISTANT_INTENT_FIELDS: Final = frozenset(
    {
        "schema_version",
        "intent_code",
        "playbook_code",
        "scope_kind",
        "scope_limit",
        "clarification_required",
        "clarification_key",
        "explanation_key",
    }
)


@dataclass(frozen=True, slots=True)
class AssistantIntent:
    schema_version: int
    intent_code: AssistantIntentCode
    playbook_code: str | None
    scope_kind: AssistantScopeKind
    scope_limit: int
    clarification_required: bool
    clarification_key: str | None
    explanation_key: str


@dataclass(frozen=True, slots=True)
class AssistantPlan:
    title_key: str
    resolved_count: int | None
    bounded_count: int | None
    control_codes: tuple[str, ...]
    not_performed_codes: tuple[str, ...]
    next_step_code: str


@dataclass(frozen=True, slots=True)
class AssistantPlanOutcome:
    result_code: AssistantResultCode
    intent: AssistantIntent | None
    plan: AssistantPlan | None
    suggestion_codes: tuple[AssistantIntentCode, ...]
    fallback_reason: AssistantFallbackReason | None = None


_EXPECTED: Final[dict[AssistantIntentCode, tuple[str | None, AssistantScopeKind, bool, str | None, str]]] = {
    AssistantIntentCode.SCOPE_OPEN_PROSPECTS: (
        None,
        AssistantScopeKind.ASSIGNED_OPEN_PROSPECTS,
        False,
        None,
        "plan_scope_open_prospects",
    ),
    AssistantIntentCode.REBALANCE_OPEN_PROSPECTS: (
        "new_prospect",
        AssistantScopeKind.ORGANIZATION_OPEN_PROSPECTS,
        False,
        None,
        "plan_rebalance_open_prospects",
    ),
    AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP: (
        "new_prospect",
        AssistantScopeKind.NEW_PROSPECTS,
        False,
        None,
        "plan_prepare_new_prospect_followup",
    ),
    AssistantIntentCode.EXPLAIN_AUTOMATION_STATUS: (
        None,
        AssistantScopeKind.AUTOMATION_STATUS,
        False,
        None,
        "plan_explain_automation_status",
    ),
    AssistantIntentCode.CLARIFY_REQUEST: (
        None,
        AssistantScopeKind.NONE,
        True,
        "clarify_assistant_request",
        "plan_clarification_required",
    ),
    AssistantIntentCode.UNSUPPORTED_REQUEST: (
        None,
        AssistantScopeKind.NONE,
        False,
        None,
        "plan_intent_not_supported",
    ),
}


def parse_assistant_intent(
    payload: Mapping[str, object],
    *,
    allowed_intents: tuple[AssistantIntentCode, ...] = ACTIVE_ASSISTANT_INTENTS,
    maximum_scope: int = 50,
) -> AssistantIntent:
    """Valide une sortie brute sans jamais conserver ni exposer sa représentation."""

    if set(payload) != ASSISTANT_INTENT_FIELDS:
        raise AssistantValidationError("La sortie Assistant ne respecte pas les propriétés autorisées.")
    if payload.get("schema_version") != 1:
        raise AssistantValidationError("La version du schéma Assistant est inconnue.")
    try:
        intent_code = AssistantIntentCode(_string(payload, "intent_code"))
        scope_kind = AssistantScopeKind(_string(payload, "scope_kind"))
    except ValueError as error:
        raise AssistantValidationError("La sortie Assistant contient un code inconnu.") from error
    if intent_code not in allowed_intents or intent_code not in _EXPECTED:
        raise AssistantValidationError("L'intention Assistant n'est pas active.")
    scope_limit = payload.get("scope_limit")
    if isinstance(scope_limit, bool) or not isinstance(scope_limit, int) or not 1 <= scope_limit <= maximum_scope:
        raise AssistantValidationError("La portée Assistant est invalide.")
    clarification_required = payload.get("clarification_required")
    if not isinstance(clarification_required, bool):
        raise AssistantValidationError("L'état de clarification Assistant est invalide.")
    playbook_code = _optional_string(payload, "playbook_code")
    clarification_key = _optional_string(payload, "clarification_key")
    explanation_key = _string(payload, "explanation_key")
    expected = _EXPECTED[intent_code]
    actual = (playbook_code, scope_kind, clarification_required, clarification_key, explanation_key)
    if actual != expected:
        raise AssistantValidationError("La sortie Assistant est incohérente.")
    return AssistantIntent(
        schema_version=1,
        intent_code=intent_code,
        playbook_code=playbook_code,
        scope_kind=scope_kind,
        scope_limit=scope_limit,
        clarification_required=clarification_required,
        clarification_key=clarification_key,
        explanation_key=explanation_key,
    )


def guided_assistant_payload(intent_code: AssistantIntentCode, *, maximum_scope: int) -> dict[str, object]:
    if intent_code not in GUIDED_ASSISTANT_INTENTS:
        raise AssistantValidationError("La suggestion Assistant est inconnue.")
    playbook, scope, clarification, clarification_key, explanation = _EXPECTED[intent_code]
    return {
        "schema_version": 1,
        "intent_code": intent_code.value,
        "playbook_code": playbook,
        "scope_kind": scope.value,
        "scope_limit": maximum_scope,
        "clarification_required": clarification,
        "clarification_key": clarification_key,
        "explanation_key": explanation,
    }


def _string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise AssistantValidationError(f"Le champ {key} est invalide.")
    return value


def _optional_string(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise AssistantValidationError(f"Le champ {key} est invalide.")
    return value
