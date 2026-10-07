from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ....application.errors import (
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    CsrfValidationFailed,
)
from ....application.ports.metrics import AutomationEvent, AutomationOperation, MetricsOutcome
from ....application.tenancy import TenantContext
from ....application.use_cases.assistant import (
    AssistantCommandInvalid,
    AssistantDisabled,
    CreateAssistantPlanCommand,
)
from ....domain.assistant_catalog import ASSISTANT_SUGGESTION_CODES, catalog_entry
from ....domain.identity import MembershipIdentity, capabilities_for
from ....infrastructure.postgres.automation_exception_resolution import (
    AutomationExceptionRejected,
    AutomationExceptionResolution,
    AutomationExceptionUnavailable,
    AutomationExceptionVersionConflict,
    ExceptionCommand,
)
from ....infrastructure.postgres.automation_lifecycle import (
    AutomationLifecycleDisabled,
    AutomationLifecycleRejected,
    AutomationLifecycleUnavailable,
    AutomationLifecycleVersionConflict,
    AutomationPlaybookLifecycle,
    LifecycleCommand,
)
from ....infrastructure.postgres.automation_preflight import (
    AutomationPreflightDisabled,
    AutomationPreflightNotConfigured,
    AutomationPreflightRejected,
    AutomationPreflightUnavailable,
)
from ....infrastructure.postgres.automation_reader import (
    AutomationReadCursorInvalid,
    AutomationReader,
    AutomationReadUnavailable,
)
from ....infrastructure.postgres.automation_settings import (
    AutomationSettingsRejected,
    AutomationSettingsUnavailable,
    AutomationSettingsVersionConflict,
)
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..responses import NO_STORE_HEADERS, api_error
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(prefix="/api/automation", tags=["automation"])


class AssistantPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    input_mode: Literal["free_text", "guided"]
    user_text: str | None = Field(default=None, max_length=500)
    suggestion_code: str | None = Field(default=None, max_length=64)


class PreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    idempotency_key: str = Field(min_length=1, max_length=128)


class LifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    idempotency_key: str = Field(min_length=1, max_length=128)


class SuspendPlaybookRequest(LifecycleRequest):
    reason_code: Literal["operator_request", "safety_review", "rollback"]


class ExceptionCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    idempotency_key: str = Field(min_length=1, max_length=128)


class ResolveExceptionRequest(ExceptionCommandRequest):
    resolution_code: Literal["human_review_complete", "canonical_record_confirmed", "no_action_required"]


class AbandonExceptionRequest(ExceptionCommandRequest):
    resolution_code: Literal["not_actionable", "duplicate_case", "expired_context"]


class SurfaceTelemetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    surface: Literal["today", "playbooks", "exceptions"]


class AutomationSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    automation_enabled: bool
    expected_version: int = Field(ge=0)


_READ_QUERY_KEYS = frozenset({"limit", "cursor", "state"})
_EXCEPTION_STATES = frozenset({"open", "in_progress", "resolved", "abandoned"})
_PLAYBOOK_CODES = frozenset({"new_prospect", "proposal_pending", "forgotten_opportunity"})


@router.get("/settings")
async def get_automation_settings(request: Request, container: ContainerDependency) -> Response:
    try:
        authentication, membership, _capabilities, context = await _settings_context(request, container)
        if container.automation_settings is None:
            raise AutomationSettingsUnavailable
        item = await container.automation_settings.get(context=context)
    except Exception as error:
        response = _settings_error(request, error)
        if response is not None:
            return response
        raise
    del authentication, membership
    return JSONResponse(
        jsonable_encoder(_settings_payload(container, item)),
        headers=NO_STORE_HEADERS,
    )


@router.get("/availability")
async def get_automation_availability(request: Request, container: ContainerDependency) -> Response:
    """Expose the tenant-scoped switch used to decide whether Automation is navigable."""
    try:
        _authentication, membership, _capabilities, context = await _read_context(request, container)
        if container.automation_settings is None:
            raise AutomationSettingsUnavailable
        item = await container.automation_settings.get(context=context)
    except Exception as error:
        response = _read_error(request, error)
        if response is not None:
            return response
        raise

    organization_enabled = bool(item.automation_enabled)
    global_enabled = bool(container.settings.automation_enabled)
    rollout_enabled = bool(container.settings.automation_rollout_enabled_for(membership.organization_id))
    assistant_enabled = bool(container.settings.automation_assistant_enabled)
    return JSONResponse(
        {
            "schema_version": 1,
            "global_enabled": global_enabled,
            "organization_enabled": organization_enabled,
            "rollout_enabled": rollout_enabled,
            "effective_enabled": global_enabled and rollout_enabled and organization_enabled,
            # The Automation workspace can remain readable while plan preparation is
            # deliberately closed. Clients must use this dedicated switch before
            # exposing the Assistant command form.
            "assistant_available": global_enabled and assistant_enabled and rollout_enabled and organization_enabled,
        },
        headers=NO_STORE_HEADERS,
    )


@router.get("/suggestions")
async def list_assistant_suggestions(request: Request, container: ContainerDependency) -> Response:
    """Expose the closed Assistant catalogue for the active tenant and locale."""
    try:
        _authentication, membership, capabilities, context = await _read_context(request, container)
        if "automation:plan:create" not in capabilities:
            raise PermissionError
        if container.automation_settings is None:
            raise AutomationSettingsUnavailable
        item = await container.automation_settings.get(context=context)
        if not _assistant_available(
            container,
            membership.organization_id,
            organization_enabled=bool(item.automation_enabled),
        ):
            raise AssistantDisabled
        items = [
            {
                "code": entry.code.value,
                "label": entry.label(membership.organization_locale),
                "prompt": entry.prompt(membership.organization_locale),
                "scope_kind": entry.scope_kind.value,
                "required_capability": entry.required_capability,
            }
            for code in ASSISTANT_SUGGESTION_CODES
            if (entry := catalog_entry(code)).required_capability in capabilities
        ]
    except AssistantDisabled:
        return api_error(request, 409, "automation_assistant_disabled", "L’assistant est désactivé.")
    except Exception as error:
        response = _read_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        {"schema_version": 1, "items": items},
        headers=NO_STORE_HEADERS,
    )


@router.get("/today")
async def get_today(request: Request, container: ContainerDependency) -> Response:
    """Expose a bounded, tenant-scoped projection of live CRM priorities."""
    try:
        _authentication, membership, capabilities, context = await _read_context(request, container)
        reader = _reader(container)
        method = getattr(reader, "get_today", None)
        payload = (
            await method(
                context,
                membership_id=membership.id,
                organization_scope="automation:read:organization" in capabilities,
                limit=5,
            )
            if method is not None
            else {"counts": {}, "items": []}
        )
    except Exception as error:
        response = _read_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(jsonable_encoder({"schema_version": 1, **payload}), headers=NO_STORE_HEADERS)


@router.patch("/settings")
async def update_automation_settings(
    payload: AutomationSettingsRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        require_json_content_type(request)
        authentication, membership, _capabilities, context = await _settings_context(request, container)
        require_trusted_origin(request, container.settings.cors_allowed_origins)
        require_csrf_token(request, authentication.identity.csrf_token)
        if container.automation_settings is None:
            raise AutomationSettingsUnavailable
        item = await container.automation_settings.update(
            context=context,
            automation_enabled=payload.automation_enabled,
            expected_version=payload.expected_version,
        )
    except Exception as error:
        response = _settings_error(request, error)
        if response is not None:
            return response
        raise
    del membership
    return JSONResponse(
        jsonable_encoder(_settings_payload(container, item)),
        headers={**NO_STORE_HEADERS, "ETag": f'"{item.version}"'},
    )


@router.get("/playbooks")
async def list_playbooks(request: Request, container: ContainerDependency) -> Response:
    try:
        authentication, membership, capabilities, context = await _read_context(request, container)
        params = _read_query(request)
        if "state" in params:
            raise ValueError("state")
        page = await _reader(container).list_playbooks(
            context,
            organization_scope="automation:read:organization" in capabilities,
            membership_id=membership.id,
            limit=_read_limit(params),
            cursor=_read_cursor(params),
        )
    except Exception as error:
        response = _read_error(request, error)
        if response is not None:
            return response
        raise
    preflight_enabled = (
        container.settings.automation_enabled
        and "automation:preflights:run" in capabilities
        and container.settings.automation_rollout_enabled_for(membership.organization_id)
    )
    lifecycle_enabled = (
        container.settings.automation_enabled
        and ("automation:playbooks:activate" in capabilities or "automation:playbooks:suspend" in capabilities)
        and container.settings.automation_rollout_enabled_for(membership.organization_id)
    )
    del authentication, membership, capabilities
    return JSONResponse(
        jsonable_encoder(
            {
                "schema_version": 1,
                "preflight_enabled": preflight_enabled,
                "lifecycle_enabled": lifecycle_enabled,
                **page,
            }
        ),
        headers=NO_STORE_HEADERS,
    )


@router.get("/playbooks/{code}")
async def get_playbook(code: str, request: Request, container: ContainerDependency) -> Response:
    try:
        if code not in _PLAYBOOK_CODES:
            raise LookupError
        _read_query(request, require_empty=True)
        authentication, membership, capabilities, context = await _read_context(request, container)
        item = await _reader(container).get_playbook(
            context,
            code=code,
            organization_scope="automation:read:organization" in capabilities,
            membership_id=membership.id,
        )
        if item is None:
            raise LookupError
    except Exception as error:
        response = _read_error(request, error)
        if response is not None:
            return response
        raise
    del authentication, membership, capabilities
    return JSONResponse(jsonable_encoder({"schema_version": 1, "item": item}), headers=NO_STORE_HEADERS)


@router.post("/playbooks/{code}/preflights")
async def run_preflight(
    code: str,
    payload: PreflightRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        if code not in _PLAYBOOK_CODES:
            raise LookupError
        require_json_content_type(request)
        authentication = await required_authentication(request, container)
        require_trusted_origin(request, container.settings.cors_allowed_origins)
        require_csrf_token(request, authentication.identity.csrf_token)
        membership = authentication.identity.active_membership
        capabilities = capabilities_for(authentication.identity.user, membership)
        if membership is None or not membership.is_active or "automation:preflights:run" not in capabilities:
            raise PermissionError
        if not container.settings.automation_rollout_enabled_for(membership.organization_id):
            raise AutomationPreflightDisabled
        if container.automation_preflight_runner is None:
            raise AutomationPreflightUnavailable
        outcome = await container.automation_preflight_runner.run(
            context=TenantContext(
                actor_id=authentication.identity.user.id,
                organization_id=membership.organization_id,
                request_id=getattr(request.state, "request_id", "unknown"),
            ),
            playbook_code=code,
            membership_id=membership.id,
            idempotency_key=payload.idempotency_key,
        )
    except Exception as error:
        response = _preflight_error(request, error)
        if response is not None:
            return response
        raise
    item = {
        "id": outcome.id,
        "playbook_code": outcome.playbook_code,
        "ruleset_version": outcome.ruleset_version,
        "state": outcome.state,
        "correlation_id": outcome.correlation_id,
        "subject_count": outcome.subject_count,
        "green_count": outcome.green_count,
        "yellow_count": outcome.yellow_count,
        "red_count": outcome.red_count,
        "to_verify_count": outcome.to_verify_count,
        "created_at": outcome.created_at,
        "updated_at": outcome.updated_at,
        "expires_at": outcome.expires_at,
    }
    _record_automation_event(
        request,
        "playbook_preflighted",
        "preflight",
        replayed=outcome.replayed,
        state=outcome.state,
    )
    return JSONResponse(
        jsonable_encoder({"schema_version": 1, "item": item, "replayed": outcome.replayed}),
        status_code=200 if outcome.replayed else 201,
        headers=NO_STORE_HEADERS,
    )


@router.post("/playbooks/{code}/activate")
async def activate_playbook(
    code: str,
    payload: LifecycleRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    return await _transition_playbook(
        code=code,
        command="activate",
        payload=payload,
        request=request,
        container=container,
    )


@router.post("/playbooks/{code}/suspend")
async def suspend_playbook(
    code: str,
    payload: SuspendPlaybookRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    return await _transition_playbook(
        code=code,
        command="suspend",
        payload=payload,
        request=request,
        container=container,
        reason_code=payload.reason_code,
    )


@router.post("/playbooks/{code}/resume")
async def resume_playbook(
    code: str,
    payload: LifecycleRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    return await _transition_playbook(
        code=code,
        command="resume",
        payload=payload,
        request=request,
        container=container,
    )


@router.get("/exceptions")
async def list_exceptions(request: Request, container: ContainerDependency) -> Response:
    try:
        authentication, membership, capabilities, context = await _read_context(request, container)
        params = _read_query(request)
        state = params.get("state")
        if state is not None and state not in _EXCEPTION_STATES:
            raise ValueError("state")
        page = await _reader(container).list_exceptions(
            context,
            membership_id=membership.id,
            organization_scope="automation:read:organization" in capabilities,
            state=state,
            limit=_read_limit(params),
            cursor=_read_cursor(params),
        )
    except Exception as error:
        response = _read_error(request, error)
        if response is not None:
            return response
        raise
    del authentication, membership, capabilities
    return JSONResponse(jsonable_encoder({"schema_version": 1, **page}), headers=NO_STORE_HEADERS)


@router.get("/exceptions/{exception_id}")
async def get_exception(exception_id: str, request: Request, container: ContainerDependency) -> Response:
    try:
        _read_query(request, require_empty=True)
        authentication, membership, capabilities, context = await _read_context(request, container)
        item = await _reader(container).get_exception(
            context,
            exception_id=_resource_id(exception_id),
            membership_id=membership.id,
            organization_scope="automation:read:organization" in capabilities,
        )
        if item is None:
            raise LookupError
    except Exception as error:
        response = _read_error(request, error)
        if response is not None:
            return response
        raise
    del authentication, membership, capabilities
    return JSONResponse(jsonable_encoder({"schema_version": 1, "item": item}), headers=NO_STORE_HEADERS)


@router.post("/exceptions/{exception_id}/claim")
async def claim_exception(
    exception_id: str,
    payload: ExceptionCommandRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    return await _transition_exception(
        exception_id=exception_id,
        command="claim",
        payload=payload,
        request=request,
        container=container,
    )


@router.post("/exceptions/{exception_id}/resolve")
async def resolve_exception(
    exception_id: str,
    payload: ResolveExceptionRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    return await _transition_exception(
        exception_id=exception_id,
        command="resolve",
        payload=payload,
        request=request,
        container=container,
        resolution_code=payload.resolution_code,
    )


@router.post("/exceptions/{exception_id}/abandon")
async def abandon_exception(
    exception_id: str,
    payload: AbandonExceptionRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    return await _transition_exception(
        exception_id=exception_id,
        command="abandon",
        payload=payload,
        request=request,
        container=container,
        resolution_code=payload.resolution_code,
    )


@router.post("/exceptions/{exception_id}/reconcile")
async def reconcile_exception(
    exception_id: str,
    payload: ExceptionCommandRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    return await _transition_exception(
        exception_id=exception_id,
        command="reconcile",
        payload=payload,
        request=request,
        container=container,
    )


@router.post("/telemetry/surfaces")
async def record_surface_opened(
    payload: SurfaceTelemetryRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    """Télémétrie de navigation sans persistance métier ni contenu utilisateur."""
    try:
        require_json_content_type(request)
        authentication = await required_authentication(request, container)
        require_trusted_origin(request, container.settings.cors_allowed_origins)
        require_csrf_token(request, authentication.identity.csrf_token)
        membership = authentication.identity.active_membership
        capabilities = capabilities_for(authentication.identity.user, membership)
        if membership is None or not membership.is_active or "automation:read:self" not in capabilities:
            raise PermissionError
        _record_automation_event(request, "surface_opened", payload.surface)
    except Exception as error:
        response = _surface_telemetry_error(request, error)
        if response is not None:
            return response
        raise
    return Response(status_code=204, headers=NO_STORE_HEADERS)


@router.get("/preflights/{preflight_id}")
async def get_preflight(preflight_id: str, request: Request, container: ContainerDependency) -> Response:
    try:
        _read_query(request, require_empty=True)
        authentication, membership, capabilities, context = await _read_context(request, container)
        item = await _reader(container).get_preflight(
            context,
            preflight_id=_resource_id(preflight_id),
            membership_id=membership.id,
            organization_scope="automation:read:organization" in capabilities,
        )
        if item is None:
            raise LookupError
    except Exception as error:
        response = _read_error(request, error)
        if response is not None:
            return response
        raise
    del authentication, membership, capabilities
    return JSONResponse(jsonable_encoder({"schema_version": 1, "item": item}), headers=NO_STORE_HEADERS)


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
                rollout_enabled=container.settings.automation_rollout_enabled_for(membership.organization_id),
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
    return JSONResponse(jsonable_encoder(_outcome_payload(outcome)), headers=NO_STORE_HEADERS)


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
                "items": [
                    {
                        "id": item.id,
                        "kind": item.kind,
                        "label": item.label,
                        "stage": item.stage,
                        "priority": item.priority,
                        "updated_at": item.updated_at,
                    }
                    for item in plan.items
                ],
                "next_cursor": plan.next_cursor,
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


async def _read_context(
    request: Request, container: ContainerDependency
) -> tuple[RequestAuthentication, MembershipIdentity, tuple[str, ...], TenantContext]:
    authentication = await required_authentication(request, container)
    membership = authentication.identity.active_membership
    capabilities = capabilities_for(authentication.identity.user, membership)
    if membership is None or not membership.is_active or "automation:read:self" not in capabilities:
        raise PermissionError
    return (
        authentication,
        membership,
        capabilities,
        TenantContext(
            actor_id=authentication.identity.user.id,
            organization_id=membership.organization_id,
            request_id=getattr(request.state, "request_id", "unknown"),
        ),
    )


async def _settings_context(
    request: Request, container: ContainerDependency
) -> tuple[RequestAuthentication, MembershipIdentity, tuple[str, ...], TenantContext]:
    authentication = await required_authentication(request, container)
    membership = authentication.identity.active_membership
    capabilities = capabilities_for(authentication.identity.user, membership)
    if membership is None or not membership.is_active or "automation:settings:manage" not in capabilities:
        raise PermissionError
    return (
        authentication,
        membership,
        capabilities,
        TenantContext(
            actor_id=authentication.identity.user.id,
            organization_id=membership.organization_id,
            request_id=getattr(request.state, "request_id", "unknown"),
        ),
    )


def _settings_payload(container: ContainerDependency, item: object) -> dict[str, object]:
    from ....infrastructure.postgres.automation_settings import AutomationSettingsView

    value = item if isinstance(item, AutomationSettingsView) else None
    assert value is not None
    return {
        "schema_version": 1,
        "item": {
            "id": value.id,
            "organization_id": value.organization_id,
            "automation_enabled": value.automation_enabled,
            "suspension_generation": value.suspension_generation,
            "version": value.version,
            "created_at": value.created_at,
            "updated_at": value.updated_at,
        },
        "global_enabled": container.settings.automation_enabled,
        "assistant_enabled": container.settings.automation_assistant_enabled,
        "assistant_available": _assistant_available(
            container,
            value.organization_id,
            organization_enabled=value.automation_enabled,
        ),
        "rollout_mode": container.settings.automation_rollout_mode,
        "effective_enabled": (
            container.settings.automation_enabled
            and container.settings.automation_rollout_enabled_for(value.organization_id)
            and value.automation_enabled
        ),
    }


def _assistant_available(
    container: ContainerDependency,
    organization_id: UUID,
    *,
    organization_enabled: bool,
) -> bool:
    """Return the single server-side eligibility rule for Assistant reads and plans."""
    return bool(
        container.settings.automation_enabled
        and container.settings.automation_assistant_enabled
        and container.settings.automation_rollout_enabled_for(organization_id)
        and organization_enabled
    )


def _reader(container: ContainerDependency) -> AutomationReader:
    if container.automation_reader is None:
        raise AutomationReadUnavailable
    return container.automation_reader


async def _transition_playbook(
    *,
    code: str,
    command: LifecycleCommand,
    payload: LifecycleRequest,
    request: Request,
    container: ContainerDependency,
    reason_code: str | None = None,
) -> Response:
    try:
        if code not in _PLAYBOOK_CODES:
            raise LookupError
        require_json_content_type(request)
        authentication = await required_authentication(request, container)
        require_trusted_origin(request, container.settings.cors_allowed_origins)
        require_csrf_token(request, authentication.identity.csrf_token)
        membership = authentication.identity.active_membership
        capabilities = capabilities_for(authentication.identity.user, membership)
        capability = "automation:playbooks:suspend" if command == "suspend" else "automation:playbooks:activate"
        if membership is None or not membership.is_active or capability not in capabilities:
            raise PermissionError
        if not container.settings.automation_rollout_enabled_for(membership.organization_id):
            raise AutomationLifecycleDisabled
        outcome = await _lifecycle(container).transition(
            context=TenantContext(
                actor_id=authentication.identity.user.id,
                organization_id=membership.organization_id,
                request_id=getattr(request.state, "request_id", "unknown"),
            ),
            playbook_code=code,
            membership_id=membership.id,
            command=command,
            expected_version=_if_match_version(request),
            idempotency_key=payload.idempotency_key,
            reason_code=reason_code,
        )
    except Exception as error:
        response = _lifecycle_error(request, error)
        if response is not None:
            return response
        raise
    item = {
        "playbook_code": outcome.playbook_code,
        "command": outcome.command,
        "state": outcome.state,
        "prepare_enabled": outcome.prepare_enabled,
        "suspension_generation": outcome.suspension_generation,
        "version": outcome.version,
        "correlation_id": outcome.correlation_id,
    }
    _record_automation_event(
        request,
        "playbook_state_changed",
        command,
        replayed=outcome.replayed,
        state=outcome.state,
        reason_code=reason_code,
    )
    return JSONResponse(
        jsonable_encoder({"schema_version": 1, "item": item, "replayed": outcome.replayed}),
        headers={**NO_STORE_HEADERS, "ETag": f'"{outcome.version}"'},
    )


def _lifecycle(container: ContainerDependency) -> AutomationPlaybookLifecycle:
    if container.automation_playbook_lifecycle is None:
        raise AutomationLifecycleUnavailable
    return container.automation_playbook_lifecycle


async def _transition_exception(
    *,
    exception_id: str,
    command: ExceptionCommand,
    payload: ExceptionCommandRequest,
    request: Request,
    container: ContainerDependency,
    resolution_code: str | None = None,
) -> Response:
    try:
        require_json_content_type(request)
        authentication = await required_authentication(request, container)
        require_trusted_origin(request, container.settings.cors_allowed_origins)
        require_csrf_token(request, authentication.identity.csrf_token)
        membership = authentication.identity.active_membership
        capabilities = capabilities_for(authentication.identity.user, membership)
        can_manage = "automation:exceptions:resolve:organization" in capabilities
        if membership is None or not membership.is_active or "automation:exceptions:resolve:self" not in capabilities:
            raise PermissionError
        outcome = await _exception_resolution(container).transition(
            context=TenantContext(
                actor_id=authentication.identity.user.id,
                organization_id=membership.organization_id,
                request_id=getattr(request.state, "request_id", "unknown"),
            ),
            exception_id=_resource_id(exception_id),
            membership_id=membership.id,
            command=command,
            expected_version=_if_match_version(request),
            idempotency_key=payload.idempotency_key,
            resolution_code=resolution_code,
            can_manage_organization=can_manage,
        )
    except Exception as error:
        response = _exception_error(request, error)
        if response is not None:
            return response
        raise
    item = {
        "id": outcome.id,
        "command": outcome.command,
        "state": outcome.state,
        "assigned_membership_id": outcome.assigned_membership_id,
        "resolution_code": outcome.resolution_code,
        "version": outcome.version,
        "correlation_id": outcome.correlation_id,
    }
    _record_automation_event(
        request,
        "exception_resolved",
        command,
        replayed=outcome.replayed,
        state=outcome.state,
    )
    return JSONResponse(
        jsonable_encoder({"schema_version": 1, "item": item, "replayed": outcome.replayed}),
        headers={**NO_STORE_HEADERS, "ETag": f'"{outcome.version}"'},
    )


def _exception_resolution(container: ContainerDependency) -> AutomationExceptionResolution:
    if container.automation_exception_resolution is None:
        raise AutomationExceptionUnavailable
    return container.automation_exception_resolution


def _if_match_version(request: Request) -> int:
    raw = request.headers.get("if-match", "")
    if len(raw) < 3 or not raw.startswith('"') or not raw.endswith('"'):
        raise ValueError("if_match")
    try:
        version = int(raw[1:-1])
    except ValueError as error:
        raise ValueError("if_match") from error
    if version < 1:
        raise ValueError("if_match")
    return version


def _read_query(request: Request, *, require_empty: bool = False) -> dict[str, str]:
    keys = [key for key, _ in request.query_params.multi_items()]
    params = dict(request.query_params)
    if len(keys) != len(set(keys)) or set(params) - _READ_QUERY_KEYS or (require_empty and params):
        raise ValueError("query")
    return params


def _read_limit(params: dict[str, str]) -> int:
    value = params.get("limit", "25")
    try:
        limit = int(value)
    except ValueError as error:
        raise ValueError("limit") from error
    if not 1 <= limit <= 100:
        raise ValueError("limit")
    return limit


def _read_cursor(params: dict[str, str]) -> UUID | None:
    value = params.get("cursor")
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError as error:
        raise AutomationReadCursorInvalid from error


def _resource_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        raise ValueError("resource_id") from error


_AUTOMATION_EVENT_NAMES: dict[AutomationEvent, str] = {
    "surface_opened": "automation.surface_opened.v1",
    "playbook_preflighted": "automation.playbook_preflighted.v1",
    "playbook_state_changed": "automation.playbook_state_changed.v1",
    "exception_resolved": "automation.exception_resolved.v1",
    "first_value_reached": "automation.first_value_reached.v1",
}
_AUTOMATION_OPERATIONS = frozenset(
    {
        "today",
        "playbooks",
        "exceptions",
        "preflight",
        "activate",
        "suspend",
        "resume",
        "claim",
        "resolve",
        "abandon",
        "reconcile",
    }
)
_AUTOMATION_STATES = frozenset(
    {
        "draft",
        "preflight_required",
        "preflight_running",
        "ready",
        "active",
        "suspended",
        "retired",
        "open",
        "in_progress",
        "resolved",
        "abandoned",
    }
)
_AUTOMATION_REASON_CODES = frozenset({"operator_request", "safety_review", "rollback"})


def _record_automation_event(
    request: Request,
    event: AutomationEvent,
    operation: AutomationOperation,
    *,
    outcome: MetricsOutcome = "accepted",
    state: str | None = None,
    replayed: bool = False,
    reason_code: str | None = None,
) -> None:
    """Émet un événement borné ; aucune charge métier ne passe dans les logs/labels."""
    safe_operation = operation if operation in _AUTOMATION_OPERATIONS else "today"
    fields: dict[str, str | int] = {
        "operation": safe_operation,
        "outcome": outcome,
        "replayed": int(replayed),
    }
    if state in _AUTOMATION_STATES:
        fields["state"] = state
    if reason_code in _AUTOMATION_REASON_CODES:
        fields["reason_code"] = reason_code
    technical_logger = getattr(request.app.state, "technical_logger", None)
    if technical_logger is not None:
        technical_logger.info(
            _AUTOMATION_EVENT_NAMES[event],
            request_id=getattr(request.state, "request_id", ""),
            **fields,
        )
    container = getattr(request.app.state, "container", None)
    metrics = getattr(container, "metrics", None)
    record_metric = getattr(metrics, "record_automation_event", None)
    if callable(record_metric):
        record_metric(
            event,
            safe_operation,
            outcome,
        )


def _surface_telemetry_error(request: Request, error: Exception) -> JSONResponse | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, AuthenticationServiceUnavailable):
        return api_error(request, 503, "authentication_unavailable", "Authentification indisponible.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "csrf_failed", "La protection de la session a refusé la requête.")
    if isinstance(error, PermissionError):
        return api_error(request, 403, "automation_telemetry_forbidden", "Télémétrie Automation non autorisée.")
    return None


def _read_error(request: Request, error: Exception) -> JSONResponse | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, AuthenticationServiceUnavailable):
        return api_error(request, 503, "authentication_unavailable", "Authentification indisponible.")
    if isinstance(error, PermissionError):
        return api_error(request, 403, "automation_read_forbidden", "Consultation Automation non autorisée.")
    if isinstance(error, (AutomationReadCursorInvalid, ValueError)):
        return api_error(request, 422, "automation_query_invalid", "Paramètres de consultation invalides.")
    if isinstance(error, LookupError):
        return api_error(request, 404, "automation_resource_not_found", "Ressource Automation introuvable.")
    if isinstance(error, AutomationReadUnavailable):
        return api_error(request, 503, "automation_read_unavailable", "Lecture Automation indisponible.")
    if isinstance(error, AutomationSettingsUnavailable):
        return api_error(
            request, 503, "automation_settings_unavailable", "Les paramètres Automation sont indisponibles."
        )
    return None


def _settings_error(request: Request, error: Exception) -> JSONResponse | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, AuthenticationServiceUnavailable):
        return api_error(request, 503, "authentication_unavailable", "Authentification indisponible.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "csrf_failed", "La protection de la session a refusé la requête.")
    if isinstance(error, (PermissionError, AutomationSettingsRejected)):
        return api_error(request, 403, "automation_settings_forbidden", "Paramètres Automation non autorisés.")
    if isinstance(error, AutomationSettingsVersionConflict):
        return api_error(
            request,
            409,
            "automation_settings_version_conflict",
            "Les paramètres Automation ont changé. Actualisez avant de réessayer.",
            fields={"version": str(error.current_version)},
        )
    if isinstance(error, AutomationSettingsUnavailable):
        return api_error(
            request, 503, "automation_settings_unavailable", "Les paramètres Automation sont indisponibles."
        )
    if isinstance(error, ValueError):
        return api_error(request, 422, "automation_settings_invalid", "Les paramètres Automation sont invalides.")
    return None


def _preflight_error(request: Request, error: Exception) -> JSONResponse | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, AuthenticationServiceUnavailable):
        return api_error(request, 503, "authentication_unavailable", "Authentification indisponible.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "csrf_failed", "La protection de la session a refusé la requête.")
    if isinstance(error, PermissionError):
        return api_error(request, 403, "automation_preflight_forbidden", "Prévol Automation non autorisé.")
    if isinstance(error, AutomationPreflightDisabled):
        return api_error(
            request, 409, "automation_preflight_disabled", "Le Prévol est désactivé dans cet environnement."
        )
    if isinstance(error, AutomationPreflightNotConfigured):
        return api_error(
            request, 409, "automation_preflight_not_configured", "Le Playbook doit être configuré avant le Prévol."
        )
    if isinstance(error, AutomationPreflightRejected):
        return api_error(request, 409, "automation_preflight_rejected", "Le Prévol a été refusé sans effet métier.")
    if isinstance(error, AutomationPreflightUnavailable):
        return api_error(request, 503, "automation_preflight_unavailable", "Le Prévol est indisponible.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "automation_preflight_invalid", "La demande de Prévol est invalide.")
    if isinstance(error, LookupError):
        return api_error(request, 404, "automation_resource_not_found", "Ressource Automation introuvable.")
    return None


def _lifecycle_error(request: Request, error: Exception) -> JSONResponse | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, AuthenticationServiceUnavailable):
        return api_error(request, 503, "authentication_unavailable", "Authentification indisponible.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "csrf_failed", "La protection de la session a refusé la requête.")
    if isinstance(error, PermissionError):
        return api_error(request, 403, "automation_lifecycle_forbidden", "Commande Playbook non autorisée.")
    if isinstance(error, AutomationLifecycleVersionConflict):
        return api_error(
            request, 412, "automation_playbook_version_conflict", "Le Playbook a été modifié. Actualisez-le."
        )
    if isinstance(error, AutomationLifecycleDisabled):
        return api_error(
            request, 409, "automation_lifecycle_disabled", "L’automatisation est désactivée dans cet environnement."
        )
    if isinstance(error, AutomationLifecycleRejected):
        return api_error(
            request,
            409,
            "automation_lifecycle_rejected",
            "La transition a été refusée : un Prévol frais et complet peut être requis.",
        )
    if isinstance(error, AutomationLifecycleUnavailable):
        return api_error(request, 503, "automation_lifecycle_unavailable", "La commande Playbook est indisponible.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "automation_lifecycle_invalid", "La commande Playbook est invalide.")
    if isinstance(error, LookupError):
        return api_error(request, 404, "automation_resource_not_found", "Ressource Automation introuvable.")
    return None


def _exception_error(request: Request, error: Exception) -> JSONResponse | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, AuthenticationServiceUnavailable):
        return api_error(request, 503, "authentication_unavailable", "Authentification indisponible.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "csrf_failed", "La protection de la session a refusé la requête.")
    if isinstance(error, PermissionError):
        return api_error(request, 403, "automation_exception_forbidden", "Commande d’exception non autorisée.")
    if isinstance(error, AutomationExceptionVersionConflict):
        return api_error(
            request, 412, "automation_exception_version_conflict", "L’exception a été modifiée. Actualisez-la."
        )
    if isinstance(error, AutomationExceptionRejected):
        return api_error(
            request,
            409,
            "automation_exception_rejected",
            "La transition d’exception a été refusée sans effet CRM ni retry automatique.",
        )
    if isinstance(error, AutomationExceptionUnavailable):
        return api_error(request, 503, "automation_exception_unavailable", "La commande d’exception est indisponible.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "automation_exception_invalid", "La commande d’exception est invalide.")
    return None
