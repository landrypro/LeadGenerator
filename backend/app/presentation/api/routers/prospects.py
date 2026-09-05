from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    CsrfValidationFailed,
    GoogleProtectionUnavailable,
    InsufficientCapability,
    InvalidGoogleSelectionGrant,
    ProspectResourceNotFound,
    ProspectServiceUnavailable,
    ProspectVersionConflict,
)
from ....application.models import GoogleAccessOwner
from ....application.tenancy import TenantContext
from ....application.use_cases import GoogleProspectInput
from ....domain.identity import capabilities_for
from ....domain.pipeline import PipelineStageView, PipelineValidationError, ProspectStageTransitionView
from ....domain.prospect import ProspectOrigin, ProspectProfilePatch
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..mappers import to_prospect_response
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import (
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
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(prefix="/api/prospects", tags=["prospects"])


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
    if isinstance(error, PipelineValidationError):
        return api_error(request, 422, "pipeline_transition_invalid", str(error))
    if isinstance(error, (AuthenticationServiceUnavailable, ProspectServiceUnavailable)):
        return api_error(request, 503, "prospects_unavailable", "Les prospects sont temporairement indisponibles.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "validation_failed", "La commande prospect est invalide.")
    return None
