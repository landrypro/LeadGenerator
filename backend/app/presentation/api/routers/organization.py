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
    InvitationAlreadyPending,
    InvitationDeliveryUnavailable,
    InvitationRateLimited,
    LastActiveAdministrator,
    MembershipAlreadyActive,
    MembershipReactivationRequired,
    MembershipVersionConflict,
    OrganizationAdministrationUnavailable,
    OrganizationNotActive,
    OrganizationResourceNotFound,
    OrganizationVersionConflict,
    ProvisioningOutcomeUnknown,
)
from ....application.tenancy import TenantContext
from ....domain.identity import MembershipRole, MembershipStatus, capabilities_for
from ....domain.organization import (
    CreateMemberInvitationCommand,
    UpdateMembershipCommand,
    UpdateOrganizationCommand,
)
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..mappers import to_member_invitation_response, to_member_response, to_organization_response
from ..responses import NO_STORE_HEADERS, api_error, delete_session_cookie
from ..schemas import (
    CreateMemberInvitationRequest,
    EmptyCommand,
    MemberInvitationPageResponse,
    MemberInvitationResponse,
    MemberPageResponse,
    MemberResponse,
    OrganizationResponse,
    ResendMemberInvitationRequest,
    UpdateMembershipRequest,
    UpdateOrganizationRequest,
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(prefix="/api/organization", tags=["organization"])


@router.get("", response_model=OrganizationResponse)
async def get_organization(request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_organization is None:
            raise OrganizationAdministrationUnavailable
        view = await container.get_organization.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "organization:read"),
        )
    except Exception as error:
        response = _organization_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_organization_response(view).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.patch("", response_model=OrganizationResponse)
async def update_organization(
    payload: UpdateOrganizationRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.update_organization is None:
            raise OrganizationAdministrationUnavailable
        view = await container.update_organization.execute(
            context=_tenant_context(request, authentication),
            command=UpdateOrganizationCommand(**payload.model_dump()),
            has_capability=_has_capability(authentication, "organization:update"),
        )
    except Exception as error:
        response = _organization_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_organization_response(view).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/members", response_model=MemberPageResponse)
async def list_members(
    request: Request,
    container: ContainerDependency,
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=25, ge=1, le=100),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_members is None:
            raise OrganizationAdministrationUnavailable
        page = await container.list_members.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "members:read"),
            cursor=cursor,
            limit=limit,
        )
    except Exception as error:
        response = _organization_error(request, error)
        if response is not None:
            return response
        raise
    payload = MemberPageResponse(
        items=[to_member_response(item) for item in page.items],
        next_cursor=page.next_cursor,
    )
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.patch("/members/{membership_id}", response_model=MemberResponse)
async def update_membership(
    membership_id: UUID,
    payload: UpdateMembershipRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.update_membership is None:
            raise OrganizationAdministrationUnavailable
        outcome = await container.update_membership.execute(
            context=_tenant_context(request, authentication),
            membership_id=membership_id,
            command=UpdateMembershipCommand(
                version=payload.version,
                role=MembershipRole(payload.role) if payload.role else None,
                status=MembershipStatus(payload.status) if payload.status else None,
            ),
            has_capability=_has_capability(authentication, "members:manage"),
        )
    except Exception as error:
        response = _organization_error(request, error)
        if response is not None:
            return response
        raise
    response = JSONResponse(to_member_response(outcome.member).model_dump(mode="json"), headers=NO_STORE_HEADERS)
    if outcome.current_user_changed:
        delete_session_cookie(response, container.settings)
    return response


@router.get("/invitations", response_model=MemberInvitationPageResponse)
async def list_invitations(
    request: Request,
    container: ContainerDependency,
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=25, ge=1, le=100),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_member_invitations is None:
            raise OrganizationAdministrationUnavailable
        page = await container.list_member_invitations.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "invitations:read"),
            cursor=cursor,
            limit=limit,
        )
    except Exception as error:
        response = _organization_error(request, error)
        if response is not None:
            return response
        raise
    payload = MemberInvitationPageResponse(
        items=[to_member_invitation_response(item) for item in page.items],
        next_cursor=page.next_cursor,
    )
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/invitations", response_model=MemberInvitationResponse)
async def create_invitation(
    payload: CreateMemberInvitationRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.create_member_invitation is None:
            raise OrganizationAdministrationUnavailable
        view = await container.create_member_invitation.execute(
            context=_tenant_context(request, authentication),
            command=CreateMemberInvitationCommand(
                email=payload.email,
                role=MembershipRole(payload.role),
                invitation_request_id=payload.invitation_request_id,
            ),
            has_capability=_has_capability(authentication, "invitations:manage"),
        )
    except Exception as error:
        response = _organization_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        to_member_invitation_response(view).model_dump(mode="json"),
        status_code=200 if view.replayed else 201,
        headers=NO_STORE_HEADERS,
    )


@router.post("/invitations/{invitation_id}/resend", response_model=MemberInvitationResponse)
async def resend_invitation(
    invitation_id: UUID,
    payload: ResendMemberInvitationRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.resend_member_invitation is None:
            raise OrganizationAdministrationUnavailable
        view = await container.resend_member_invitation.execute(
            context=_tenant_context(request, authentication),
            invitation_id=invitation_id,
            resend_request_id=payload.resend_request_id,
            has_capability=_has_capability(authentication, "invitations:manage"),
        )
    except Exception as error:
        response = _organization_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_member_invitation_response(view).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.delete("/invitations/{invitation_id}", response_model=MemberInvitationResponse)
async def revoke_invitation(
    invitation_id: UUID,
    payload: EmptyCommand,
    request: Request,
    container: ContainerDependency,
) -> Response:
    del payload
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.revoke_member_invitation is None:
            raise OrganizationAdministrationUnavailable
        view = await container.revoke_member_invitation.execute(
            context=_tenant_context(request, authentication),
            invitation_id=invitation_id,
            has_capability=_has_capability(authentication, "invitations:manage"),
        )
    except Exception as error:
        response = _organization_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_member_invitation_response(view).model_dump(mode="json"), headers=NO_STORE_HEADERS)


async def _authenticated_mutation(request: Request, container: ContainerDependency) -> RequestAuthentication:
    require_json_content_type(request)
    require_trusted_origin(request, container.settings.cors_allowed_origins)
    authentication = await required_authentication(request, container)
    require_csrf_token(request, authentication.identity.csrf_token)
    return authentication


def _tenant_context(request: Request, authentication: RequestAuthentication) -> TenantContext:
    membership = authentication.identity.active_membership
    if membership is None:
        raise InsufficientCapability
    return TenantContext(
        actor_id=authentication.identity.user.id,
        organization_id=membership.organization_id,
        request_id=getattr(request.state, "request_id", "unknown"),
    )


def _has_capability(authentication: RequestAuthentication, capability: str) -> bool:
    return capability in capabilities_for(authentication.identity.user, authentication.identity.active_membership)


def _organization_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "request_rejected", "La requête a été refusée.")
    if isinstance(error, InsufficientCapability):
        return api_error(request, 403, "insufficient_capability", "Autorisation insuffisante.")
    if isinstance(error, OrganizationResourceNotFound):
        return api_error(request, 404, "organization_resource_not_found", "Ressource introuvable.")
    if isinstance(error, OrganizationVersionConflict):
        return api_error(
            request,
            409,
            "organization_version_conflict",
            "L’organisation a été modifiée.",
            fields=_version_field(error.current_version),
        )
    if isinstance(error, MembershipVersionConflict):
        return api_error(
            request,
            409,
            "membership_version_conflict",
            "L’appartenance a été modifiée.",
            fields=_version_field(error.current_version),
        )
    if isinstance(error, LastActiveAdministrator):
        return api_error(
            request,
            409,
            "last_active_administrator",
            "L’organisation doit conserver au moins un Administrateur actif.",
        )
    if isinstance(error, IdempotencyKeyReused):
        return api_error(request, 409, "idempotency_key_reused", "La clé de requête a déjà été utilisée.")
    if isinstance(error, MembershipAlreadyActive):
        return api_error(request, 409, "membership_already_active", "Cette personne est déjà membre.")
    if isinstance(error, MembershipReactivationRequired):
        return api_error(
            request,
            409,
            "membership_reactivation_required",
            "Cette appartenance doit être réactivée explicitement.",
        )
    if isinstance(error, InvitationAlreadyPending):
        return api_error(request, 409, "invitation_already_pending", "Une invitation est déjà en attente.")
    if isinstance(error, InvitationAlreadyAccepted):
        return api_error(request, 409, "invitation_already_accepted", "L’invitation a déjà été acceptée.")
    if isinstance(error, OrganizationNotActive):
        return api_error(request, 409, "organization_not_active", "L’organisation n’est pas active.")
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
            "invitation_outcome_unknown",
            "Le résultat a peut-être été validé. Répétez la même clé de requête.",
        )
    if isinstance(error, (AuthenticationServiceUnavailable, OrganizationAdministrationUnavailable)):
        return api_error(
            request,
            503,
            "organization_administration_unavailable",
            "L’administration de l’organisation est temporairement indisponible.",
        )
    if isinstance(error, ValueError):
        return api_error(request, 422, "validation_failed", "La commande est invalide.")
    return None


def _version_field(current_version: int | None) -> dict[str, str]:
    return {"version": str(current_version)} if current_version is not None else {}
