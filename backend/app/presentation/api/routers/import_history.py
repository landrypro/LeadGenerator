"""Phase 4.3: minimized history, separate from raw CSV preview routes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ....application.errors import AuthenticationRequired
from ....application.tenancy import TenantContext
from ....domain.identity import capabilities_for
from ....infrastructure.postgres.import_history import ImportHistoryReader
from ..dependencies import ContainerDependency, required_authentication
from ..responses import NO_STORE_HEADERS, api_error

router = APIRouter(tags=["imports"])


def _valid_period(start: datetime | None, end: datetime | None) -> bool:
    return not ((start and start.tzinfo is None) or (end and end.tzinfo is None) or (start and end and end <= start))


async def _reader_context(
    request: Request, container: ContainerDependency
) -> tuple[ImportHistoryReader, TenantContext] | Response:
    try:
        auth = await required_authentication(request, container)
    except AuthenticationRequired:
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    membership = auth.identity.active_membership
    if (
        membership is None
        or not membership.is_active
        or "imports:read" not in capabilities_for(auth.identity.user, membership)
    ):
        return api_error(request, 403, "insufficient_capability", "Lecture des imports non autorisée.")
    if container.import_history is None:
        return api_error(request, 503, "imports_unavailable", "L’historique est indisponible.")
    return container.import_history, TenantContext(
        actor_id=auth.identity.user.id,
        organization_id=membership.organization_id,
        request_id=getattr(request.state, "request_id", "unknown"),
    )


def _response(payload: object) -> Response:
    return JSONResponse(jsonable_encoder(payload), headers=NO_STORE_HEADERS)


@router.get("/api/csv-import-sessions")
async def list_sessions(
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: UUID | None = None,
    status: str | None = None,
    declaration_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    author_id: UUID | None = None,
) -> Response:
    if status is not None and status not in {"uploaded", "mapped", "validated", "confirmed", "expired"}:
        return api_error(request, 422, "invalid_status", "Statut invalide.")
    if not _valid_period(created_from, created_to):
        return api_error(request, 422, "invalid_period", "Période invalide.")
    result = await _reader_context(request, container)
    if isinstance(result, Response):
        return result
    reader, context = result
    try:
        return _response(
            await reader.list_sessions(
                context,
                limit=limit,
                cursor=cursor,
                status=status,
                declaration_id=declaration_id,
                created_from=created_from,
                created_to=created_to,
                author_id=author_id,
            )
        )
    except LookupError:
        return api_error(request, 404, "resource_not_found", "Curseur introuvable.")


@router.get("/api/csv-import-sessions/{session_id}")
async def get_session(session_id: UUID, request: Request, container: ContainerDependency) -> Response:
    result = await _reader_context(request, container)
    if isinstance(result, Response):
        return result
    reader, context = result
    row = await reader.get_session(context, session_id)
    return _response(row) if row is not None else api_error(request, 404, "resource_not_found", "Session introuvable.")


@router.get("/api/csv-import-runs")
async def list_runs(
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: UUID | None = None,
    declaration_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    author_id: UUID | None = None,
) -> Response:
    if not _valid_period(created_from, created_to):
        return api_error(request, 422, "invalid_period", "Période invalide.")
    result = await _reader_context(request, container)
    if isinstance(result, Response):
        return result
    reader, context = result
    try:
        return _response(
            await reader.list_runs(
                context,
                limit=limit,
                cursor=cursor,
                declaration_id=declaration_id,
                created_from=created_from,
                created_to=created_to,
                author_id=author_id,
            )
        )
    except LookupError:
        return api_error(request, 404, "resource_not_found", "Curseur introuvable.")


@router.get("/api/csv-import-runs/{run_id}")
async def get_run(run_id: UUID, request: Request, container: ContainerDependency) -> Response:
    result = await _reader_context(request, container)
    if isinstance(result, Response):
        return result
    reader, context = result
    row = await reader.get_run(context, run_id)
    return _response(row) if row is not None else api_error(request, 404, "resource_not_found", "Lot introuvable.")
