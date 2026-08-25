from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    CsrfValidationFailed,
    InsufficientCapability,
    InvalidGoogleSelectionGrant,
    ProspectResourceNotFound,
    ProspectServiceUnavailable,
    ProspectVersionConflict,
)
from ....application.models import GoogleAccessOwner
from ....application.tenancy import TenantContext
from ....domain.identity import capabilities_for
from ....domain.prospect import ProspectOrigin, ProspectProfilePatch
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..mappers import to_prospect_response
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import (
    CreateProspectRequest,
    ProspectFromGoogleItemResponse,
    ProspectFromGoogleRequest,
    ProspectFromGoogleResponse,
    ProspectPageResponse,
    ProspectProfileUpdateRequest,
    ProspectResponse,
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(prefix="/api/prospects", tags=["prospects"])


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
            place_ids=tuple(payload.place_ids),
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
    if isinstance(error, ProspectResourceNotFound):
        return api_error(request, 404, "prospect_not_found", "Prospect introuvable.")
    if isinstance(error, ProspectVersionConflict):
        return api_error(request, 409, "optimistic_lock_conflict", "Le prospect a changé depuis sa lecture.")
    if isinstance(error, (AuthenticationServiceUnavailable, ProspectServiceUnavailable)):
        return api_error(request, 503, "prospects_unavailable", "Les prospects sont temporairement indisponibles.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "validation_failed", "La commande prospect est invalide.")
    return None
