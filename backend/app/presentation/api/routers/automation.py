from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ....application.errors import AuthenticationRequired, CsrfValidationFailed
from ....application.tenancy import TenantContext
from ....application.use_cases.assistant import (
    AssistantCommandInvalid,
    AssistantDisabled,
    CreateAssistantPlanCommand,
)
from ....domain.identity import capabilities_for
from ..dependencies import ContainerDependency, required_authentication
from ..responses import NO_STORE_HEADERS, api_error
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(prefix="/api/automation", tags=["automation"])


class AssistantPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    input_mode: Literal["free_text", "guided"]
    user_text: str | None = Field(default=None, max_length=500)
    suggestion_code: str | None = Field(default=None, max_length=64)


@router.post("/intent-plans")
async def create_intent_plan(
    payload: AssistantPlanRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        require_json_content_type(request)
        authentication = await required_authentication(request, container)
        require_trusted_origin(request, container.settings.cors_allowed_origins)
        require_csrf_token(request, authentication.identity.csrf_token)
        membership = authentication.identity.active_membership
        capabilities = capabilities_for(authentication.identity.user, membership)
        if membership is None or not membership.is_active or "automation:plan:create" not in capabilities:
            raise PermissionError
        if container.create_assistant_plan is None:
            raise RuntimeError("assistant_unavailable")
        outcome = await container.create_assistant_plan.execute(
            CreateAssistantPlanCommand(
                context=TenantContext(
                    actor_id=authentication.identity.user.id,
                    organization_id=membership.organization_id,
                    request_id=getattr(request.state, "request_id", "unknown"),
                ),
                membership_id=membership.id,
                locale=membership.organization_locale,
                input_mode=payload.input_mode,
                user_text=payload.user_text,
                suggestion_code=payload.suggestion_code,
                can_read_organization="automation:read:organization" in capabilities,
            )
        )
    except AuthenticationRequired:
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    except CsrfValidationFailed:
        return api_error(request, 403, "csrf_failed", "La protection de la session a refusé la requête.")
    except PermissionError:
        return api_error(request, 403, "automation_plan_forbidden", "Plan Assistant non autorisé.")
    except AssistantDisabled:
        return api_error(request, 409, "automation_assistant_disabled", "L’assistant est désactivé.")
    except AssistantCommandInvalid as error:
        return api_error(
            request,
            422,
            "assistant_command_invalid",
            str(error),
            fields={"user_text": str(error)},
        )
    except RuntimeError as error:
        if str(error) != "assistant_unavailable":
            raise
        return api_error(request, 503, "assistant_unavailable", "L’assistant est indisponible.")
    return JSONResponse(_outcome_payload(outcome), headers=NO_STORE_HEADERS)


def _outcome_payload(outcome: object) -> dict[str, object]:
    from ....domain.assistant import AssistantPlanOutcome

    value = outcome if isinstance(outcome, AssistantPlanOutcome) else None
    assert value is not None
    intent = value.intent
    plan = value.plan
    return {
        "schema_version": 1,
        "result_code": value.result_code.value,
        "intent": (
            {
                "intent_code": intent.intent_code.value,
                "playbook_code": intent.playbook_code,
                "scope_kind": intent.scope_kind.value,
                "scope_limit": intent.scope_limit,
                "clarification_required": intent.clarification_required,
                "clarification_key": intent.clarification_key,
                "explanation_key": intent.explanation_key,
            }
            if intent
            else None
        ),
        "plan": (
            {
                "title_key": plan.title_key,
                "resolved_count": plan.resolved_count,
                "bounded_count": plan.bounded_count,
                "control_codes": list(plan.control_codes),
                "not_performed_codes": list(plan.not_performed_codes),
                "next_step_code": plan.next_step_code,
            }
            if plan
            else None
        ),
        "suggestion_codes": [code.value for code in value.suggestion_codes],
        "fallback_reason": value.fallback_reason.value if value.fallback_reason else None,
    }
