from __future__ import annotations

import hmac
from urllib.parse import urlsplit

from fastapi import Request

from ...application.errors import CsrfValidationFailed


def require_json_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if content_type != "application/json":
        raise CsrfValidationFailed


def require_trusted_origin(request: Request, allowed_origins: tuple[str, ...]) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        referer = request.headers.get("referer", "")
        parsed = urlsplit(referer)
        origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    if origin.rstrip("/") not in {allowed.rstrip("/") for allowed in allowed_origins}:
        raise CsrfValidationFailed


def require_csrf_token(request: Request, expected_token: str) -> None:
    supplied_token = request.headers.get("x-csrf-token", "")
    if not supplied_token or not hmac.compare_digest(supplied_token, expected_token):
        raise CsrfValidationFailed
