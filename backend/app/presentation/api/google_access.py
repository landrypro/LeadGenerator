from __future__ import annotations

from fastapi import Request, Response

from ...application.errors import (
    ActiveOrganizationRequired,
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    CsrfValidationFailed,
    InsufficientCapability,
    JsonContentTypeRequired,
)
from ...application.models import GoogleAccessContext
from ...container import AppContainer
from ...domain.identity import capabilities_for
from .dependencies import required_authentication
from .responses import api_error
from .security import require_csrf_token, require_json_content_type, require_trusted_origin


async def required_google_access(
    request: Request,
    container: AppContainer,
    capability: str,
) -> GoogleAccessContext:
    require_json_content_type(request, strict_http_status=True)
    require_trusted_origin(request, container.settings.cors_allowed_origins)
    authentication = await required_authentication(request, container)
    membership = authentication.identity.active_membership
    if membership is None or not membership.is_active:
        raise ActiveOrganizationRequired
    if capability not in capabilities_for(authentication.identity.user, membership):
        raise InsufficientCapability
    require_csrf_token(request, authentication.identity.csrf_token)
    return GoogleAccessContext(
        user_id=authentication.identity.user.id,
        organization_id=membership.organization_id,
        membership_id=membership.id,
    )


def google_access_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, ActiveOrganizationRequired):
        return api_error(request, 403, "active_organization_required", "Une organisation active est requise.")
    if isinstance(error, InsufficientCapability):
        return api_error(request, 403, "insufficient_capability", "Autorisation Google insuffisante.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "request_rejected", "La requête a été refusée.")
    if isinstance(error, JsonContentTypeRequired):
        return api_error(request, 415, "json_required", "Le type application/json est obligatoire.")
    if isinstance(error, AuthenticationServiceUnavailable):
        return api_error(
            request,
            503,
            "authentication_unavailable",
            "L’authentification est temporairement indisponible.",
        )
    return None
