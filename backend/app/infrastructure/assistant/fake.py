from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from ...application.ports.assistant import AssistantInterpretationRequest, AssistantProviderUnavailable
from ...domain.assistant import AssistantIntentCode, guided_assistant_payload


class FakeAssistantInterpreter:
    """Faux fournisseur local : corpus fermé, déterministe et sans dépendance technique."""

    def __init__(self, *, failure_mode: str | None = None) -> None:
        if failure_mode not in {None, "unavailable", "invalid"}:
            raise ValueError("Le mode de panne fake est inconnu.")
        self._failure_mode = failure_mode

    async def interpret(self, request: AssistantInterpretationRequest) -> Mapping[str, object]:
        if self._failure_mode == "unavailable":
            raise AssistantProviderUnavailable
        if self._failure_mode == "invalid":
            return {"schema_version": 1, "intent_code": "invalid", "extra": request.request_id}
        normalized = _normalize(request.user_text_ephemeral)
        code = _classify(normalized)
        if code.value not in request.allowed_intent_codes:
            code = AssistantIntentCode.UNSUPPORTED_REQUEST
        return (
            guided_assistant_payload(code, maximum_scope=request.maximum_scope_hint)
            if code
            in {
                AssistantIntentCode.SCOPE_OPEN_PROSPECTS,
                AssistantIntentCode.REBALANCE_OPEN_PROSPECTS,
                AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP,
            }
            else _non_guided_payload(code, request.maximum_scope_hint)
        )


def _classify(text: str) -> AssistantIntentCode:
    forbidden = (
        "ignore toutes les regles",
        "ignore all rules",
        "permission",
        "role administrateur",
        "admin role",
        "envoi immediat",
        "send immediately",
        "workflow libre",
        "custom workflow",
    )
    if any(value in text for value in forbidden):
        return AssistantIntentCode.UNSUPPORTED_REQUEST
    if any(
        value in text
        for value in ("proposition en attente", "pending proposal", "occasion oubliee", "forgotten opportunity")
    ):
        return AssistantIntentCode.UNSUPPORTED_REQUEST
    if any(
        value in text
        for value in ("statut automatisation", "etat automatisation", "automation status", "prevol", "feu")
    ):
        return AssistantIntentCode.EXPLAIN_AUTOMATION_STATUS
    if any(
        value in text for value in ("repart", "redistrib", "charge", "entre mon equipe", "among my team", "rebalance")
    ):
        return AssistantIntentCode.REBALANCE_OPEN_PROSPECTS
    if any(
        value in text for value in ("relance", "suivi", "follow up", "follow-up", "nouveaux prospects", "new prospects")
    ):
        return AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP
    if any(
        value in text for value in ("prospects en cours", "prospects ouverts", "open prospects", "current prospects")
    ):
        return AssistantIntentCode.SCOPE_OPEN_PROSPECTS
    return AssistantIntentCode.CLARIFY_REQUEST


def _non_guided_payload(code: AssistantIntentCode, maximum_scope: int) -> dict[str, object]:
    values = {
        AssistantIntentCode.EXPLAIN_AUTOMATION_STATUS: (
            "automation_status",
            False,
            None,
            "plan_explain_automation_status",
        ),
        AssistantIntentCode.CLARIFY_REQUEST: (
            "none",
            True,
            "clarify_assistant_request",
            "plan_clarification_required",
        ),
        AssistantIntentCode.UNSUPPORTED_REQUEST: (
            "none",
            False,
            None,
            "plan_intent_not_supported",
        ),
    }
    scope, clarification, clarification_key, explanation = values[code]
    return {
        "schema_version": 1,
        "intent_code": code.value,
        "playbook_code": None,
        "scope_kind": scope,
        "scope_limit": maximum_scope,
        "clarification_required": clarification,
        "clarification_key": clarification_key,
        "explanation_key": explanation,
    }


def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(character for character in folded if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", without_marks).strip()
