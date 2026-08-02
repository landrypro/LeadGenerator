from __future__ import annotations

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from ...config import Settings

NO_STORE_HEADERS = {"Cache-Control": "no-store, max-age=0"}


def api_error(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    fields: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response_headers = {**NO_STORE_HEADERS, **(headers or {})}
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", ""),
                "fields": fields or {},
            }
        },
        headers=response_headers,
    )


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def delete_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
