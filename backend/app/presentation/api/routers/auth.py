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
from ..schemas import AuthenticationResponse, LoginRequest
from ..security import require_json_content_type, require_trusted_origin

router = APIRouter(prefix="/api/auth", tags=["authentication"])
NO_STORE_HEADERS = {"Cache-Control": "no-store, max-age=0"}


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
        return _error(request, 403, "request_rejected", "La requête de connexion a été refusée.")
    except InvalidCredentials:
        return _error(request, 401, "invalid_credentials", "Courriel ou mot de passe incorrect.")
    except LoginRateLimited as error:
        return _error(
            request,
            429,
            "login_rate_limited",
            "Trop de tentatives. Réessayez plus tard.",
            headers={"Retry-After": str(error.retry_after_seconds)},
        )
    except AuthenticationServiceUnavailable:
        return _error(request, 503, "authentication_unavailable", "L’authentification est temporairement indisponible.")

    response = JSONResponse(
        to_authentication_response(outcome.identity).model_dump(mode="json"), headers=NO_STORE_HEADERS
    )
    response.set_cookie(
        key=container.settings.session_cookie_name,
        value=outcome.session.token,
        httponly=True,
        secure=container.settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/me", response_model=AuthenticationResponse)
async def me(request: Request, container: ContainerDependency) -> Response:
    token = request.cookies.get(container.settings.session_cookie_name, "")
    if not token:
        return _error(request, 401, "authentication_required", "Authentification requise.")
    if container.get_current_session is None:
        return _error(request, 503, "authentication_unavailable", "L’authentification est temporairement indisponible.")
    try:
        identity = await container.get_current_session.execute(token)
    except AuthenticationRequired:
        return _error(request, 401, "authentication_required", "Authentification requise.")
    except AuthenticationServiceUnavailable:
        return _error(request, 503, "authentication_unavailable", "L’authentification est temporairement indisponible.")
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
        return _error(request, 403, "csrf_failed", "La protection de la session a refusé la requête.")
    except AuthenticationRequired:
        response = _error(request, 401, "authentication_required", "Authentification requise.")
        _delete_session_cookie(response, container)
        return response
    except AuthenticationServiceUnavailable:
        return _error(request, 503, "authentication_unavailable", "L’authentification est temporairement indisponible.")

    logout_response = Response(status_code=204, headers=NO_STORE_HEADERS)
    _delete_session_cookie(logout_response, container)
    return logout_response


def _delete_session_cookie(response: Response, container: ContainerDependency) -> None:
    response.delete_cookie(
        key=container.settings.session_cookie_name,
        path="/",
        secure=container.settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _error(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response_headers = {**NO_STORE_HEADERS, **(headers or {})}
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
                "fields": {},
            }
        },
        headers=response_headers,
    )
