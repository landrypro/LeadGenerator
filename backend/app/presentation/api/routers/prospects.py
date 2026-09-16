from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    ActivityResourceNotFound,
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    CsrfValidationFailed,
    GoogleProtectionUnavailable,
    InsufficientCapability,
    InvalidGoogleSelectionGrant,
    ProspectArchivedReadOnly,
    ProspectResourceNotFound,
    ProspectServiceUnavailable,
    ProspectVersionConflict,
    TaskResourceNotFound,
    TaskVersionConflict,
)
from ....application.models import GoogleAccessOwner
from ....application.tenancy import TenantContext
from ....application.use_cases import GoogleProspectInput
from ....domain.activity import (
    ActivityDirection,
    ActivityType,
    ProspectActivityDraft,
    ProspectActivityView,
    ProspectTaskDraft,
    ProspectTaskEventView,
    ProspectTaskView,
    TaskEventType,
    TaskPriority,
)
from ....domain.identity import capabilities_for
from ....domain.pipeline import PipelineStageView, PipelineValidationError, ProspectStageTransitionView
from ....domain.prospect import ProspectOrigin, ProspectProfilePatch
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..mappers import to_prospect_response
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import (
    ActivityCorrectionRequest,
    ActivityCreateRequest,
    CreateProspectRequest,
    PipelineBoardResponse,
    PipelineColumnPageResponse,
    PipelineStageResponse,
    PipelineStageUpdateRequest,
    ProspectFromGoogleItemResponse,
    ProspectFromGoogleRequest,
    ProspectFromGoogleResponse,
    ProspectPageResponse,
    ProspectProfileUpdateRequest,
    ProspectResponse,
    ProspectStageTransitionPageResponse,
    ProspectStageTransitionRequest,
    ProspectStageTransitionResponse,
    ReopenProspectRequest,
    TaskActionRequest,
    TaskCreateRequest,
    TaskUpdateRequest,
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(prefix="/api/prospects", tags=["prospects"])


@router.get("/{prospect_id}/timeline")
async def list_timeline(
    prospect_id: UUID,
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_prospect_timeline is None:
            raise ProspectServiceUnavailable
        page = await container.list_prospect_timeline.execute(
            context=_tenant_context(request, authentication),
            prospect_id=prospect_id,
            limit=limit,
            has_capability=_has_capability(authentication, "activities:read"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        {
            "activities": [_activity_payload(item) for item in page.activities],
            "tasks": [_task_payload(item) for item in page.tasks],
            "task_events": [_task_event_payload(item) for item in page.task_events],
            "transitions": [_timeline_transition_payload(item) for item in page.transitions],
        },
        headers=NO_STORE_HEADERS,
    )


@router.post("/{prospect_id}/activities", status_code=201)
async def create_activity(
    prospect_id: UUID, payload: ActivityCreateRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.create_activity is None:
            raise ProspectServiceUnavailable
        draft = ProspectActivityDraft(
            prospect_id=prospect_id,
            activity_type=ActivityType(payload.activity_type),
            direction=ActivityDirection(payload.direction),
            summary=payload.summary,
            note=payload.note,
            occurred_at=payload.occurred_at,
            contact_channel_id=payload.contact_channel_id,
            idempotency_key=payload.idempotency_key,
            command_fingerprint=_command_fingerprint(payload.model_dump(mode="json")),
        )
        activity = await container.create_activity.execute(
            context=_tenant_context(request, authentication),
            draft=draft,
            has_capability=_has_capability(authentication, "activities:create"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_activity_payload(activity), status_code=201, headers=NO_STORE_HEADERS)


@router.post("/activities/{activity_id}/corrections", status_code=201)
async def correct_activity(
    activity_id: UUID, payload: ActivityCorrectionRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.create_activity is None:
            raise ProspectServiceUnavailable
        activity = await container.create_activity.correct(
            context=_tenant_context(request, authentication),
            activity_id=activity_id,
            summary=payload.summary,
            note=payload.note,
            occurred_at=payload.occurred_at,
            correction_reason=payload.correction_reason,
            idempotency_key=payload.idempotency_key,
            can_correct_any=_has_capability(authentication, "activities:correct:any"),
            can_correct_self=_has_capability(authentication, "activities:correct:self"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_activity_payload(activity), status_code=201, headers=NO_STORE_HEADERS)


@router.post("/{prospect_id}/tasks", status_code=201)
async def create_task(
    prospect_id: UUID, payload: TaskCreateRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.create_task is None:
            raise ProspectServiceUnavailable
        task = await container.create_task.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "tasks:create"),
            draft=ProspectTaskDraft(
                prospect_id=prospect_id,
                title=payload.title,
                description=payload.description,
                due_at=payload.due_at,
                reminder_at=payload.reminder_at,
                priority=TaskPriority(payload.priority),
                assigned_membership_id=payload.assigned_membership_id
                or (
                    authentication.identity.active_membership.id
                    if authentication.identity.active_membership is not None
                    else None
                ),
                idempotency_key=payload.idempotency_key,
                command_fingerprint=_command_fingerprint(payload.model_dump(mode="json")),
            ),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_task_payload(task), status_code=201, headers=NO_STORE_HEADERS)


@router.get("/tasks")
async def list_tasks(
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
    prospect_id: UUID | None = None,
    status: str | None = Query(default=None, pattern="^(open|completed|cancelled)$"),
    due_before: datetime | None = None,
    mine: bool = False,
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_tasks is None:
            raise ProspectServiceUnavailable
        tasks = await container.list_tasks.execute(
            context=_tenant_context(request, authentication),
            limit=limit,
            prospect_id=prospect_id,
            status=status,
            due_before=due_before,
            assigned_membership_id=(
                authentication.identity.active_membership.id
                if mine and authentication.identity.active_membership is not None
                else None
            ),
            has_capability=_has_capability(authentication, "tasks:read"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    now = datetime.now(UTC)
    return JSONResponse({"items": [_task_payload(item, now=now) for item in tasks]}, headers=NO_STORE_HEADERS)


@router.get("/tasks/reminders/due")
async def list_due_reminders(
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
    mine: bool = True,
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_due_reminders is None:
            raise ProspectServiceUnavailable
        tasks = await container.list_due_reminders.execute(
            context=_tenant_context(request, authentication),
            limit=limit,
            has_capability=_has_capability(authentication, "tasks:read"),
            assigned_membership_id=(
                authentication.identity.active_membership.id
                if mine and authentication.identity.active_membership is not None
                else None
            ),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    now = datetime.now(UTC)
    return JSONResponse({"items": [_task_payload(item, now=now) for item in tasks]}, headers=NO_STORE_HEADERS)


@router.get("/tasks/next-actions")
async def list_next_actions(
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=500, ge=1, le=500),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_next_actions is None:
            raise ProspectServiceUnavailable
        tasks = await container.list_next_actions.execute(
            context=_tenant_context(request, authentication),
            limit=limit,
            has_capability=_has_capability(authentication, "tasks:read"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    now = datetime.now(UTC)
    return JSONResponse({"items": [_task_payload(item, now=now) for item in tasks]}, headers=NO_STORE_HEADERS)


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: UUID, payload: TaskUpdateRequest, request: Request, container: ContainerDependency
) -> Response:
    changes = {
        name: value
        for name, value in payload.model_dump(exclude={"version", "idempotency_key"}, exclude_none=True).items()
    }
    return await _task_mutation(
        task_id, payload.version, payload.idempotency_key, changes, None, TaskEventType.UPDATED, request, container
    )


@router.post("/tasks/{task_id}/{action}")
async def task_action(
    task_id: UUID, action: str, payload: TaskActionRequest, request: Request, container: ContainerDependency
) -> Response:
    actions = {
        "complete": (TaskEventType.COMPLETED, {"status": "completed", "completed_at": "__now__"}),
        "cancel": (
            TaskEventType.CANCELLED,
            {"status": "cancelled", "cancelled_at": "__now__", "cancelled_reason": payload.reason},
        ),
        "reopen": (
            TaskEventType.REOPENED,
            {"status": "open", "completed_at": None, "cancelled_at": None, "cancelled_reason": None},
        ),
        "acknowledge-reminder": (TaskEventType.REMINDER_ACKNOWLEDGED, {"reminder_acknowledged_at": "__now__"}),
        "snooze-reminder": (TaskEventType.REMINDER_SNOOZED, {"reminder_snoozed_until": payload.reminder_at}),
    }
    if action not in actions:
        return api_error(request, 404, "task_action_not_found", "Action de tâche introuvable.")
    event_type, changes = actions[action]
    return await _task_mutation(
        task_id,
        payload.version,
        payload.idempotency_key,
        cast(dict[str, object], changes),
        payload.reason,
        event_type,
        request,
        container,
    )


@router.get("/pipeline/stages", response_model=list[PipelineStageResponse])
async def list_pipeline_stages(request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_pipeline_stages is None:
            raise ProspectServiceUnavailable
        stages = await container.list_pipeline_stages.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "pipeline:read"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse([_stage_response(stage).model_dump(mode="json") for stage in stages], headers=NO_STORE_HEADERS)


@router.get("/pipeline/board", response_model=PipelineBoardResponse)
async def get_pipeline_board(
    request: Request,
    container: ContainerDependency,
    search_text: str | None = Query(default=None, max_length=160),
    owner_id: UUID | None = None,
    priority: int | None = Query(default=None, ge=0, le=5),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_pipeline_board is None:
            raise ProspectServiceUnavailable
        board = await container.get_pipeline_board.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "pipeline:read"),
            search_text=search_text,
            owner_id=owner_id,
            priority=priority,
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    payload = PipelineBoardResponse(
        stages=[_stage_response(stage) for stage in board.stages],
        columns={key: [to_prospect_response(item) for item in items] for key, items in board.columns.items()},
        next_cursors=board.next_cursors,
    )
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/pipeline/board/columns/{stage_code}", response_model=PipelineColumnPageResponse)
async def get_pipeline_column(
    stage_code: str,
    request: Request,
    container: ContainerDependency,
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=25, ge=1, le=25),
    search_text: str | None = Query(default=None, max_length=160),
    owner_id: UUID | None = None,
    priority: int | None = Query(default=None, ge=0, le=5),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_pipeline_column is None:
            raise ProspectServiceUnavailable
        page = await container.list_pipeline_column.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "pipeline:read"),
            stage_code=stage_code,
            cursor=cursor,
            limit=limit,
            search_text=search_text,
            owner_id=owner_id,
            priority=priority,
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    payload = PipelineColumnPageResponse(
        items=[to_prospect_response(item) for item in page.items], next_cursor=page.next_cursor
    )
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.patch("/pipeline/stages/{stage_code}", response_model=PipelineStageResponse)
async def update_pipeline_stage(
    stage_code: str, payload: PipelineStageUpdateRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.update_pipeline_stage is None:
            raise ProspectServiceUnavailable
        stage = await container.update_pipeline_stage.execute(
            context=_tenant_context(request, authentication),
            stage_code=stage_code,
            expected_version=payload.version,
            color_token=payload.color_token,
            labels=payload.labels,
            has_capability=_has_capability(authentication, "pipeline:configure"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_stage_response(stage).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("", response_model=ProspectPageResponse)
async def list_prospects(
    request: Request,
    container: ContainerDependency,
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=25, ge=1, le=100),
    include_archived: bool = Query(default=False),
    search_text: str | None = Query(default=None, max_length=160),
    origin: ProspectOrigin | None = None,
    owner_id: UUID | None = None,
    priority: int | None = Query(default=None, ge=0, le=5),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_prospects is None:
            raise ProspectServiceUnavailable
        page = await container.list_prospects.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "prospects:read"),
            cursor=cursor,
            limit=limit,
            include_archived=include_archived,
            search_text=search_text,
            origin=origin.value if origin is not None else None,
            owner_id=owner_id,
            priority=priority,
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    payload = ProspectPageResponse(
        items=[to_prospect_response(item) for item in page.items],
        next_cursor=page.next_cursor,
    )
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("", response_model=ProspectResponse)
async def create_prospect(
    payload: CreateProspectRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.create_manual_prospect is None:
            raise ProspectServiceUnavailable
        prospect = await container.create_manual_prospect.execute(
            context=_tenant_context(request, authentication),
            internal_alias=payload.internal_alias,
            has_capability=_has_capability(authentication, "prospects:create"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        to_prospect_response(prospect).model_dump(mode="json"), status_code=201, headers=NO_STORE_HEADERS
    )


@router.post("/from-google", response_model=ProspectFromGoogleResponse)
async def create_prospects_from_google(
    payload: ProspectFromGoogleRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.add_google_prospects is None:
            raise ProspectServiceUnavailable
        context = _tenant_context(request, authentication)
        outcome = await container.add_google_prospects.execute(
            context=context,
            owner=GoogleAccessOwner(
                user_id=authentication.identity.user.id,
                organization_id=context.organization_id,
            ),
            selection_token=payload.selection_token,
            items=tuple(
                GoogleProspectInput(place_id=item.place_id, internal_alias=item.internal_alias)
                for item in payload.items
            ),
            has_capability=_has_capability(authentication, "prospects:create"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    payload_response = ProspectFromGoogleResponse(
        items=[
            ProspectFromGoogleItemResponse(
                place_id=item.place_id,
                disposition=item.disposition,  # type: ignore[arg-type]
                prospect=to_prospect_response(item.prospect),
            )
            for item in outcome.items
        ]
    )
    return JSONResponse(payload_response.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/{prospect_id}", response_model=ProspectResponse)
async def get_prospect(prospect_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_prospect is None:
            raise ProspectServiceUnavailable
        prospect = await container.get_prospect.execute(
            context=_tenant_context(request, authentication),
            prospect_id=prospect_id,
            has_capability=_has_capability(authentication, "prospects:read"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_prospect_response(prospect).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/{prospect_id}/stage-transitions", response_model=ProspectStageTransitionResponse)
async def move_prospect_stage(
    prospect_id: UUID, payload: ProspectStageTransitionRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.move_prospect_stage is None:
            raise ProspectServiceUnavailable
        _prospect, transition = await container.move_prospect_stage.execute(
            context=_tenant_context(request, authentication),
            prospect_id=prospect_id,
            expected_version=payload.version,
            to_stage=payload.to_stage,
            reason_code=payload.reason_code,
            reason_note=payload.reason_note,
            idempotency_key=payload.idempotency_key,
            has_capability=_has_capability(authentication, "pipeline:move"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_transition_response(transition).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/{prospect_id}/stage-transitions", response_model=ProspectStageTransitionPageResponse)
async def list_prospect_stage_transitions(
    prospect_id: UUID, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_prospect_stage_transitions is None:
            raise ProspectServiceUnavailable
        items = await container.list_prospect_stage_transitions.execute(
            context=_tenant_context(request, authentication),
            prospect_id=prospect_id,
            has_capability=_has_capability(authentication, "pipeline:history:read"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        ProspectStageTransitionPageResponse(items=[_transition_response(item) for item in items]).model_dump(
            mode="json"
        ),
        headers=NO_STORE_HEADERS,
    )


@router.post("/{prospect_id}/reopen", response_model=ProspectStageTransitionResponse)
async def reopen_prospect(
    prospect_id: UUID, payload: ReopenProspectRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.reopen_prospect is None:
            raise ProspectServiceUnavailable
        _prospect, transition = await container.reopen_prospect.execute(
            context=_tenant_context(request, authentication),
            prospect_id=prospect_id,
            expected_version=payload.version,
            reason_code=payload.reason_code,
            reason_note=payload.reason_note,
            idempotency_key=payload.idempotency_key,
            has_capability=_has_capability(authentication, "pipeline:reopen"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_transition_response(transition).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.patch("/{prospect_id}", response_model=ProspectResponse)
async def update_prospect_profile(
    prospect_id: UUID,
    payload: ProspectProfileUpdateRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.update_prospect_profile is None:
            raise ProspectServiceUnavailable
        prospect = await container.update_prospect_profile.execute(
            context=_tenant_context(request, authentication),
            prospect_id=prospect_id,
            expected_version=payload.version,
            patch=ProspectProfilePatch(
                internal_alias=payload.internal_alias,
                industry_label=payload.industry_label,
                segment_code=payload.segment_code,
                size_band=payload.size_band,
                address_line_1=payload.address_line_1,
                address_line_2=payload.address_line_2,
                city=payload.city,
                region=payload.region,
                postal_code=payload.postal_code,
                country_code=payload.country_code,
                tags=tuple(payload.tags) if payload.tags is not None else None,
                owner_id=payload.owner_id,
                priority=payload.priority,
            ),
            purpose=payload.purpose,
            territory=payload.territory,
            has_capability=_has_capability(authentication, "prospects:update"),
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_prospect_response(prospect).model_dump(mode="json"), headers=NO_STORE_HEADERS)


def _stage_response(stage: PipelineStageView) -> PipelineStageResponse:
    return PipelineStageResponse(
        code=stage.code.value,
        position=stage.position,
        color_token=stage.color_token,
        labels=dict(stage.labels),
        version=stage.version,
    )


def _transition_response(transition: ProspectStageTransitionView) -> ProspectStageTransitionResponse:
    return ProspectStageTransitionResponse(
        id=transition.id,
        prospect_id=transition.prospect_id,
        actor_id=transition.actor_id,
        from_stage=transition.from_stage.value,
        to_stage=transition.to_stage.value,
        from_version=transition.from_version,
        resulting_version=transition.resulting_version,
        reason_code=transition.reason_code,
        reason_note=transition.reason_note,
        occurred_at=transition.occurred_at,
    )


async def _authenticated_mutation(request: Request, container: ContainerDependency) -> RequestAuthentication:
    require_json_content_type(request)
    require_trusted_origin(request, container.settings.cors_allowed_origins)
    authentication = await required_authentication(request, container)
    require_csrf_token(request, authentication.identity.csrf_token)
    return authentication


def _tenant_context(request: Request, authentication: RequestAuthentication) -> TenantContext:
    membership = authentication.identity.active_membership
    if membership is None or not membership.is_active:
        raise InsufficientCapability
    return TenantContext(
        actor_id=authentication.identity.user.id,
        organization_id=membership.organization_id,
        request_id=getattr(request.state, "request_id", "unknown"),
    )


def _has_capability(authentication: RequestAuthentication, capability: str) -> bool:
    return capability in capabilities_for(authentication.identity.user, authentication.identity.active_membership)


def _prospect_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "request_rejected", "La requête a été refusée.")
    if isinstance(error, InsufficientCapability):
        return api_error(request, 403, "insufficient_capability", "Autorisation prospects insuffisante.")
    if isinstance(error, InvalidGoogleSelectionGrant):
        return api_error(request, 400, "google_selection_invalid", "La sélection Google n’est plus utilisable.")
    if isinstance(error, GoogleProtectionUnavailable):
        return api_error(
            request,
            503,
            "google_protection_unavailable",
            "La protection temporaire du parcours Google est indisponible.",
        )
    if isinstance(error, ProspectResourceNotFound):
        return api_error(request, 404, "prospect_not_found", "Prospect introuvable.")
    if isinstance(error, ProspectVersionConflict):
        return api_error(request, 409, "optimistic_lock_conflict", "Le prospect a changé depuis sa lecture.")
    if isinstance(error, TaskResourceNotFound):
        return api_error(request, 404, "task_not_found", "Tâche introuvable.")
    if isinstance(error, ActivityResourceNotFound):
        return api_error(request, 404, "activity_not_found", "Activité introuvable.")
    if isinstance(error, TaskVersionConflict):
        return api_error(request, 409, "task_version_conflict", "La tâche a changé depuis sa lecture.")
    if isinstance(error, ProspectArchivedReadOnly):
        return api_error(
            request, 409, "prospect_archived_read_only", "Le prospect est archivé et ne peut pas être modifié."
        )
    if isinstance(error, PipelineValidationError):
        return api_error(request, 422, "pipeline_transition_invalid", str(error))
    if isinstance(error, (AuthenticationServiceUnavailable, ProspectServiceUnavailable)):
        return api_error(request, 503, "prospects_unavailable", "Les prospects sont temporairement indisponibles.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "validation_failed", "La commande prospect est invalide.")
    return None


async def _task_mutation(
    task_id: UUID,
    version: int,
    idempotency_key: str,
    changes: dict[str, object],
    reason: str | None,
    event_type: TaskEventType,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.update_task is None:
            raise ProspectServiceUnavailable
        task = await container.update_task.execute(
            context=_tenant_context(request, authentication),
            task_id=task_id,
            expected_version=version,
            changes=changes,
            idempotency_key=idempotency_key,
            can_manage=_has_capability(authentication, "tasks:manage"),
            can_update_assigned=_has_capability(authentication, "tasks:update:assigned"),
            current_membership_id=authentication.identity.active_membership.id
            if authentication.identity.active_membership is not None
            else None,
            action=event_type,
            reason=reason,
        )
    except Exception as error:
        response = _prospect_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_task_payload(task), headers=NO_STORE_HEADERS)


def _activity_payload(activity: ProspectActivityView) -> dict[str, object]:
    return {
        "id": str(activity.id),
        "prospect_id": str(activity.prospect_id),
        "actor_id": str(activity.actor_id),
        "activity_type": activity.activity_type.value,
        "direction": activity.direction.value,
        "summary": activity.summary,
        "note": activity.note,
        "occurred_at": activity.occurred_at.isoformat(),
        "created_at": activity.created_at.isoformat(),
        "contact_channel_id": str(activity.contact_channel_id) if activity.contact_channel_id else None,
        "permission_snapshot": activity.permission_snapshot.value,
        "correction_of_activity_id": str(activity.correction_of_activity_id)
        if activity.correction_of_activity_id
        else None,
        "correction_reason": activity.correction_reason,
    }


def _task_payload(task: ProspectTaskView, *, now: datetime | None = None) -> dict[str, object]:
    now = now or datetime.now(UTC)
    return {
        "id": str(task.id),
        "prospect_id": str(task.prospect_id),
        "title": task.title,
        "description": task.description,
        "priority": task.priority.value,
        "status": task.status.value,
        "due_at": task.due_at.isoformat(),
        "reminder_at": task.reminder_at.isoformat() if task.reminder_at else None,
        "reminder_acknowledged_at": task.reminder_acknowledged_at.isoformat()
        if task.reminder_acknowledged_at
        else None,
        "reminder_snoozed_until": task.reminder_snoozed_until.isoformat() if task.reminder_snoozed_until else None,
        "is_overdue": task.status.value == "open" and task.due_at < now,
        "assigned_membership_is_active": task.assigned_membership_is_active,
        "version": task.version,
    }


def _task_event_payload(event: ProspectTaskEventView) -> dict[str, object]:
    return {
        "id": str(event.id),
        "prospect_id": str(event.prospect_id),
        "task_id": str(event.task_id),
        "actor_id": str(event.actor_id),
        "event_type": event.event_type.value,
        "resulting_status": event.resulting_status.value,
        "resulting_version": event.resulting_version,
        "occurred_at": event.occurred_at.isoformat(),
        "reason": event.reason,
    }


def _timeline_transition_payload(transition: ProspectStageTransitionView) -> dict[str, object]:
    return {
        "id": str(transition.id),
        "prospect_id": str(transition.prospect_id),
        "actor_id": str(transition.actor_id),
        "from_stage": transition.from_stage.value,
        "to_stage": transition.to_stage.value,
        "occurred_at": transition.occurred_at.isoformat(),
    }


def _command_fingerprint(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
