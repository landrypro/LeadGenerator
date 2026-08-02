from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    AuthenticationServiceUnavailable,
    CsrfValidationFailed,
    InvitationAccountMismatch,
    InvitationAuthenticationRequired,
    InvitationInvalid,
    InvitationRateLimited,
    MembershipReactivationRequired,
    ProvisioningServiceUnavailable,
    SessionConflict,
    SessionCreationFailedAfterAcceptance,
)
from ....application.use_cases import NewAccountInvitationCommand
from ..dependencies import ContainerDependency, optional_authentication
from ..mappers import to_authentication_response
from ..responses import NO_STORE_HEADERS, api_error, set_session_cookie
from ..schemas import (
    AcceptInvitationRequest,
    AuthenticationResponse,
    InvitationPreviewRequest,
    InvitationPreviewResponse,
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(prefix="/api/auth/invitations", tags=["invitations"])


@router.post("/preview", response_model=InvitationPreviewResponse)
async def preview_invitation(
    payload: InvitationPreviewRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        require_json_content_type(request)
        require_trusted_origin(request, container.settings.cors_allowed_origins)
        if container.preview_invitation is None:
            raise ProvisioningServiceUnavailable
        preview = await container.preview_invitation.execute(
            token=payload.token,
            client_address=request.client.host if request.client else "unknown",
        )
    except Exception as error:
        response = _invitation_error(request, error)
        if response is not None:
            return response
        raise
    response_payload = InvitationPreviewResponse(
        organization_name=preview.organization_name,
        role=preview.role.value,
        expires_at=preview.expires_at,
        existing_account=preview.existing_account,
    )
    return JSONResponse(response_payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/accept", response_model=AuthenticationResponse)
async def accept_invitation(
    payload: AcceptInvitationRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        require_json_content_type(request)
        require_trusted_origin(request, container.settings.cors_allowed_origins)
        if container.accept_invitation is None:
            raise ProvisioningServiceUnavailable
        authentication = await optional_authentication(request, container)
        client_address = request.client.host if request.client else "unknown"
        if payload.new_account is not None:
            if authentication is not None:
                raise SessionConflict
            outcome = await container.accept_invitation.execute_new_account(
                token=payload.token,
                command=NewAccountInvitationCommand(
                    display_name=payload.new_account.display_name,
                    password=payload.new_account.password,
                ),
                client_address=client_address,
            )
        else:
            if authentication is None:
                raise InvitationAuthenticationRequired
            require_csrf_token(request, authentication.identity.csrf_token)
            outcome = await container.accept_invitation.execute_existing_account(
                token=payload.token,
                identity=authentication.identity,
                current_session_token=authentication.token,
                request_id=getattr(request.state, "request_id", "unknown"),
                client_address=client_address,
            )
    except Exception as error:
        response = _invitation_error(request, error)
        if response is not None:
            return response
        raise
    response = JSONResponse(
        to_authentication_response(outcome.identity).model_dump(mode="json"),
        headers=NO_STORE_HEADERS,
    )
    set_session_cookie(response, container.settings, outcome.session.token)
    return response


def _invitation_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, InvitationInvalid):
        return api_error(request, 400, "invitation_invalid", "L’invitation n’est pas utilisable.")
    if isinstance(error, InvitationAuthenticationRequired):
        return api_error(
            request,
            401,
            "invitation_authentication_required",
            "Connectez-vous avec le compte destinataire de l’invitation.",
        )
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "request_rejected", "La requête a été refusée.")
    if isinstance(error, InvitationAccountMismatch):
        return api_error(
            request,
            403,
            "invitation_account_mismatch",
            "La session active ne correspond pas à cette invitation.",
        )
    if isinstance(error, (SessionConflict, MembershipReactivationRequired)):
        code = "session_conflict" if isinstance(error, SessionConflict) else "membership_reactivation_required"
        return api_error(request, 409, code, "Cette invitation nécessite une action préalable sur le compte.")
    if isinstance(error, InvitationRateLimited):
        return api_error(
            request,
            429,
            "invitation_rate_limited",
            "Trop de tentatives. Réessayez plus tard.",
            headers={"Retry-After": str(error.retry_after_seconds)},
        )
    if isinstance(error, SessionCreationFailedAfterAcceptance):
        return api_error(
            request,
            503,
            "session_creation_failed_after_acceptance",
            "L’invitation est acceptée. Reconnectez-vous lorsque le service sera disponible.",
        )
    if isinstance(error, (AuthenticationServiceUnavailable, ProvisioningServiceUnavailable)):
        return api_error(
            request,
            503,
            "invitation_service_unavailable",
            "Le service d’invitation est temporairement indisponible.",
        )
    if isinstance(error, ValueError):
        return api_error(request, 422, "validation_failed", "La commande d’acceptation est invalide.")
    return None
