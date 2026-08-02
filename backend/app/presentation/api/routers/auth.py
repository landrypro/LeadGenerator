from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    CsrfValidationFailed,
    InvalidCredentials,
    LoginRateLimited,
)
from ..dependencies import ContainerDependency
from ..mappers import to_authentication_response
from ..responses import NO_STORE_HEADERS, api_error, delete_session_cookie, set_session_cookie
from ..schemas import AuthenticationResponse, LoginRequest
from ..security import require_json_content_type, require_trusted_origin

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/login", response_model=AuthenticationResponse)
async def login(payload: LoginRequest, request: Request, container: ContainerDependency) -> Response:
    try:
        require_json_content_type(request)
        require_trusted_origin(request, container.settings.cors_allowed_origins)
        if container.login is None:
            raise AuthenticationServiceUnavailable
        outcome = await container.login.execute(
            email=payload.email,
            password=payload.password,
            client_address=request.client.host if request.client else "unknown",
        )
    except CsrfValidationFailed:
        return api_error(request, 403, "request_rejected", "La requête de connexion a été refusée.")
    except InvalidCredentials:
        return api_error(request, 401, "invalid_credentials", "Courriel ou mot de passe incorrect.")
    except LoginRateLimited as error:
        return api_error(
            request,
            429,
            "login_rate_limited",
            "Trop de tentatives. Réessayez plus tard.",
            headers={"Retry-After": str(error.retry_after_seconds)},
        )
    except AuthenticationServiceUnavailable:
        return api_error(
            request, 503, "authentication_unavailable", "L’authentification est temporairement indisponible."
        )

    response = JSONResponse(
        to_authentication_response(outcome.identity).model_dump(mode="json"), headers=NO_STORE_HEADERS
    )
    set_session_cookie(response, container.settings, outcome.session.token)
    return response


@router.get("/me", response_model=AuthenticationResponse)
async def me(request: Request, container: ContainerDependency) -> Response:
    token = request.cookies.get(container.settings.session_cookie_name, "")
    if not token:
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if container.get_current_session is None:
        return api_error(
            request, 503, "authentication_unavailable", "L’authentification est temporairement indisponible."
        )
    try:
        identity = await container.get_current_session.execute(token)
    except AuthenticationRequired:
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    except AuthenticationServiceUnavailable:
        return api_error(
            request, 503, "authentication_unavailable", "L’authentification est temporairement indisponible."
        )
    return JSONResponse(to_authentication_response(identity).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/logout", status_code=204)
async def logout(request: Request, container: ContainerDependency) -> Response:
    token = request.cookies.get(container.settings.session_cookie_name, "")
    csrf_token = request.headers.get("x-csrf-token", "")
    try:
        require_json_content_type(request)
        require_trusted_origin(request, container.settings.cors_allowed_origins)
        if not token:
            raise AuthenticationRequired
        if container.logout is None:
            raise AuthenticationServiceUnavailable
        await container.logout.execute(token=token, csrf_token=csrf_token)
    except CsrfValidationFailed:
        return api_error(request, 403, "csrf_failed", "La protection de la session a refusé la requête.")
    except AuthenticationRequired:
        response = api_error(request, 401, "authentication_required", "Authentification requise.")
        delete_session_cookie(response, container.settings)
        return response
    except AuthenticationServiceUnavailable:
        return api_error(
            request, 503, "authentication_unavailable", "L’authentification est temporairement indisponible."
        )

    logout_response = Response(status_code=204, headers=NO_STORE_HEADERS)
    delete_session_cookie(logout_response, container.settings)
    return logout_response
