from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    CsrfValidationFailed,
    IdempotencyKeyReused,
    InsufficientCapability,
    InvitationAlreadyAccepted,
    InvitationDeliveryUnavailable,
    InvitationRateLimited,
    ProvisioningOutcomeUnknown,
    ProvisioningResourceNotFound,
    ProvisioningServiceUnavailable,
)
from ....application.tenancy import ActorContext
from ....domain.identity import capabilities_for
from ....domain.provisioning import ProvisionOrganizationCommand
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..mappers import to_provisioning_response
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import (
    CreateOrganizationRequest,
    EmptyCommand,
    PlatformOrganizationPageResponse,
    ProvisioningResponse,
    ResendInitialInvitationRequest,
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(prefix="/api/platform", tags=["platform"])


@router.get("/organizations", response_model=PlatformOrganizationPageResponse)
async def list_organizations(
    request: Request,
    container: ContainerDependency,
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=25, ge=1, le=100),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_platform_organizations is None:
            raise ProvisioningServiceUnavailable
        page = await container.list_platform_organizations.execute(
            context=_actor_context(request, authentication.identity.user.id),
            has_platform_capability="platform:organizations:read"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
            cursor=cursor,
            limit=limit,
        )
    except AuthenticationRequired:
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    except InsufficientCapability:
        return api_error(request, 403, "insufficient_capability", "Autorisation plateforme insuffisante.")
    except ValueError:
        return api_error(request, 422, "validation_failed", "Le curseur de pagination est invalide.")
    except (AuthenticationServiceUnavailable, ProvisioningServiceUnavailable):
        return api_error(request, 503, "provisioning_unavailable", "Le provisioning est temporairement indisponible.")
    payload = PlatformOrganizationPageResponse(
        items=[to_provisioning_response(item) for item in page.items],
        next_cursor=page.next_cursor,
    )
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/organizations", response_model=ProvisioningResponse)
async def create_organization(
    payload: CreateOrganizationRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.create_organization is None:
            raise ProvisioningServiceUnavailable
        view = await container.create_organization.execute(
            context=_actor_context(request, authentication.identity.user.id),
            command=ProvisionOrganizationCommand(**payload.model_dump()),
            has_platform_capability="platform:organizations:create"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
        )
    except Exception as error:
        response = _platform_error(request, error)
        if response is not None:
            return response
        raise
    response_payload = to_provisioning_response(view)
    return JSONResponse(
        response_payload.model_dump(mode="json"),
        status_code=200 if view.replayed else 201,
        headers=NO_STORE_HEADERS,
    )


@router.post("/organizations/{organization_id}/first-invitation/resend", response_model=ProvisioningResponse)
async def resend_initial_invitation(
    organization_id: UUID,
    payload: ResendInitialInvitationRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.resend_initial_invitation is None:
            raise ProvisioningServiceUnavailable
        view = await container.resend_initial_invitation.execute(
            context=_actor_context(request, authentication.identity.user.id),
            organization_id=organization_id,
            resend_request_id=payload.resend_request_id,
            has_platform_capability="platform:organizations:create"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
        )
    except Exception as error:
        response = _platform_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_provisioning_response(view).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/organizations/{organization_id}/first-invitation/revoke", response_model=ProvisioningResponse)
async def revoke_initial_invitation(
    organization_id: UUID,
    payload: EmptyCommand,
    request: Request,
    container: ContainerDependency,
) -> Response:
    del payload
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.revoke_initial_invitation is None:
            raise ProvisioningServiceUnavailable
        view = await container.revoke_initial_invitation.execute(
            context=_actor_context(request, authentication.identity.user.id),
            organization_id=organization_id,
            has_platform_capability="platform:organizations:create"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
        )
    except Exception as error:
        response = _platform_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_provisioning_response(view).model_dump(mode="json"), headers=NO_STORE_HEADERS)


async def _authenticated_mutation(
    request: Request,
    container: ContainerDependency,
) -> RequestAuthentication:
    require_json_content_type(request)
    require_trusted_origin(request, container.settings.cors_allowed_origins)
    authentication = await required_authentication(request, container)
    require_csrf_token(request, authentication.identity.csrf_token)
    return authentication


def _actor_context(request: Request, actor_id: UUID) -> ActorContext:
    return ActorContext(actor_id=actor_id, request_id=getattr(request.state, "request_id", "unknown"))


def _platform_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "request_rejected", "La requête a été refusée.")
    if isinstance(error, InsufficientCapability):
        return api_error(request, 403, "insufficient_capability", "Autorisation plateforme insuffisante.")
    if isinstance(error, ProvisioningResourceNotFound):
        return api_error(request, 404, "provisioning_not_found", "Ressource de provisioning introuvable.")
    if isinstance(error, IdempotencyKeyReused):
        return api_error(request, 409, "idempotency_key_reused", "La clé de requête a déjà été utilisée.")
    if isinstance(error, InvitationAlreadyAccepted):
        return api_error(request, 409, "invitation_already_accepted", "L’invitation a déjà été acceptée.")
    if isinstance(error, InvitationRateLimited):
        return api_error(
            request,
            429,
            "invitation_rate_limited",
            "Trop de renvois. Réessayez plus tard.",
            headers={"Retry-After": str(error.retry_after_seconds)},
        )
    if isinstance(error, InvitationDeliveryUnavailable):
        return api_error(
            request,
            503,
            "invitation_delivery_unavailable",
            "La livraison des invitations n’est pas configurée.",
        )
    if isinstance(error, ProvisioningOutcomeUnknown):
        return api_error(
            request,
            503,
            "provisioning_outcome_unknown",
            "Le résultat a peut-être été validé. Répétez la même clé de requête.",
        )
    if isinstance(error, (AuthenticationServiceUnavailable, ProvisioningServiceUnavailable)):
        return api_error(request, 503, "provisioning_unavailable", "Le provisioning est temporairement indisponible.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "validation_failed", "La commande de provisioning est invalide.")
    return None
