"""Private, tenant-scoped CSV exports."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ....application.errors import AuthenticationRequired, CsrfValidationFailed
from ....application.tenancy import TenantContext
from ....infrastructure.postgres.export_service import (
    ExportCapacityExceeded,
    ExportConflict,
    ExportExpired,
    ExportForbidden,
    ExportNotFound,
    ExportService,
)
from ..dependencies import ContainerDependency, required_authentication
from ..responses import NO_STORE_HEADERS, api_error
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(tags=["exports"])


class ExportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str
    scope: str
    filters: dict[str, str] = Field(default_factory=dict)
    columns: list[str] | None = None


class SourceExportRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acquisition_id: UUID | None = None
    provider_id: UUID | None = None
    data_category: str
    field_codes: list[str]
    purpose: str
    status: str
    valid_from: datetime
    valid_until: datetime | None = None
    evidence_ref: str
    expected_version: int | None = None


async def _context(
    request: Request, container: ContainerDependency, *, mutate: bool = False
) -> tuple[ExportService, TenantContext, UUID, str]:
    if mutate:
        require_json_content_type(request)
        require_trusted_origin(request, container.settings.cors_allowed_origins)
    auth = await required_authentication(request, container)
    if mutate:
        require_csrf_token(request, auth.identity.csrf_token)
    membership = auth.identity.active_membership
    if membership is None or not membership.is_active:
        raise ExportForbidden
    if container.exports is None:
        raise RuntimeError("exports_unavailable")
    context = TenantContext(
        actor_id=auth.identity.user.id,
        organization_id=membership.organization_id,
        request_id=getattr(request.state, "request_id", "unknown"),
    )
    return container.exports, context, membership.id, membership.organization_timezone


def _error(request: Request, error: Exception) -> Response:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, (ExportForbidden, CsrfValidationFailed)):
        return api_error(request, 403, "authorization_revoked", "Export non autorisé.")
    if isinstance(error, ExportNotFound):
        return api_error(request, 404, "resource_not_found", "Export introuvable.")
    if isinstance(error, ExportExpired):
        return api_error(request, 410, "artifact_expired", "Export expiré.")
    if isinstance(error, ExportCapacityExceeded):
        return api_error(request, 429, "limit_exceeded", "Capacité d’export atteinte.")
    if isinstance(error, ExportConflict):
        return api_error(request, 409, "export_conflict", "Demande incompatible ou export indisponible.")
    if isinstance(error, ValueError):
        code = str(error) if str(error) in {"invalid_column", "invalid_filter", "scope_forbidden"} else "invalid_export"
        return api_error(request, 422, code, "Demande d’export invalide.")
    if isinstance(error, RuntimeError) and str(error) == "exports_unavailable":
        return api_error(request, 503, "exports_unavailable", "Service d’export indisponible.")
    raise error


def _json(payload: object, *, status_code: int = 200) -> Response:
    return JSONResponse(jsonable_encoder(payload), status_code=status_code, headers=NO_STORE_HEADERS)


@router.post("/api/exports")
async def create_export(
    payload: ExportCreateRequest,
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Response:
    try:
        service, context, membership_id, timezone_name = await _context(request, container, mutate=True)
        if not idempotency_key:
            raise ValueError("invalid_idempotency_key")
        result = await service.create(
            context=context,
            membership_id=membership_id,
            timezone_name=timezone_name,
            dataset_code=payload.dataset,
            scope=payload.scope,
            filters=payload.filters,
            columns=payload.columns,
            idempotency_key=idempotency_key,
        )
        return _json(result, status_code=202)
    except Exception as error:
        return _error(request, error)


@router.get("/api/exports")
async def list_exports(
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: UUID | None = None,
) -> Response:
    try:
        service, context, membership_id, _ = await _context(request, container)
        return _json(await service.list(context, membership_id, limit=limit, cursor=cursor))
    except Exception as error:
        return _error(request, error)


@router.get("/api/exports/{export_id}")
async def get_export(export_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        service, context, membership_id, _ = await _context(request, container)
        return _json(await service.get(context, membership_id, export_id))
    except Exception as error:
        return _error(request, error)


@router.get("/api/exports/{export_id}/download")
async def download_export(export_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        service, context, membership_id, _ = await _context(request, container)
        path, dataset, byte_size = await service.download(context, membership_id, export_id)
        return FileResponse(
            path,
            media_type="text/csv; charset=utf-8",
            filename=f"marketteo-{dataset}-{export_id}.csv",
            headers={**NO_STORE_HEADERS, "X-Content-Type-Options": "nosniff", "Content-Length": str(byte_size)},
        )
    except Exception as error:
        return _error(request, error)


@router.get("/api/export-source-rules")
async def list_source_rules(request: Request, container: ContainerDependency) -> Response:
    try:
        service, context, membership_id, _ = await _context(request, container)
        return _json(await service.list_rules(context, membership_id))
    except Exception as error:
        return _error(request, error)


@router.put("/api/export-source-rules/{rule_id}")
async def update_source_rule(
    rule_id: UUID, payload: SourceExportRuleRequest, request: Request, container: ContainerDependency
) -> Response:
    return await _set_rule(payload, request, container, rule_id=rule_id)


@router.post("/api/export-source-rules")
async def create_source_rule(
    payload: SourceExportRuleRequest, request: Request, container: ContainerDependency
) -> Response:
    return await _set_rule(payload, request, container)


async def _set_rule(
    payload: SourceExportRuleRequest, request: Request, container: ContainerDependency, *, rule_id: UUID | None = None
) -> Response:
    try:
        service, context, membership_id, _ = await _context(request, container, mutate=True)
        result = await service.set_rule(
            context=context,
            membership_id=membership_id,
            acquisition_id=payload.acquisition_id,
            provider_id=payload.provider_id,
            category=payload.data_category,
            field_codes=payload.field_codes,
            purpose=payload.purpose,
            status=payload.status,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            evidence_ref=payload.evidence_ref,
            rule_id=rule_id,
            expected_version=payload.expected_version,
        )
        return _json(result, status_code=201 if rule_id is None else 200)
    except Exception as error:
        return _error(request, error)
