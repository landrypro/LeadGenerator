from __future__ import annotations

import secrets
from typing import cast

from fastapi import APIRouter, Request, Response

from ....infrastructure.observability import PrometheusMetricsRecorder
from ..dependencies import ContainerDependency

router = APIRouter(tags=["internal"])
_HEADERS = {"Cache-Control": "no-store, max-age=0", "X-Robots-Tag": "noindex, nofollow"}


@router.get("/internal/metrics", include_in_schema=False)
async def metrics(request: Request, container: ContainerDependency) -> Response:
    token = _bearer_token(request.headers.get("authorization", ""))
    configured_token = container.settings.metrics_bearer_token
    if (
        not container.settings.metrics_enabled
        or not configured_token
        or not token
        or not secrets.compare_digest(token, configured_token)
    ):
        _technical_logger(request).warning("metrics_access_denied", request_id=getattr(request.state, "request_id", ""))
        return Response(status_code=404, headers=_HEADERS)
    exporter = cast(PrometheusMetricsRecorder | None, container.metrics_exporter)
    if exporter is None:
        return Response(status_code=404, headers=_HEADERS)
    return Response(content=exporter.render(), media_type="text/plain; version=0.0.4; charset=utf-8", headers=_HEADERS)


def _bearer_token(value: str) -> str:
    prefix = "Bearer "
    return value[len(prefix) :] if value.startswith(prefix) else ""


def _technical_logger(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.technical_logger
