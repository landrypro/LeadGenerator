from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from ....application.errors import AuthenticationRequired, CsrfValidationFailed, InsufficientCapability
from ....application.tenancy import TenantContext
from ....domain.identity import capabilities_for
from ....infrastructure.postgres.connector_management import (
    ConnectorContractConflict,
    ConnectorContractNotFound,
)
from ....infrastructure.postgres.connector_pilot import MetaWebhookRejected
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..responses import NO_STORE_HEADERS, api_error
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter()


class MetaConnectorCreateRequest(BaseModel):
    provider_id: UUID
    acquisition_id: UUID
    form_id: str = Field(min_length=1, max_length=128)
    evidence_ref: str | None = Field(default=None, max_length=256)
    requested_permissions: list[str] = Field(min_length=1, max_length=3)
    allow_full_name: bool
    allow_email: bool = False
    allow_phone: bool = False
    email_permission_status: str = "unknown"
    phone_permission_status: str = "unknown"


class ConnectorVersionRequest(BaseModel):
    version: int = Field(ge=1)


class MetaConnectorReviewRequest(ConnectorVersionRequest):
    approve: bool
    approved_permissions: list[str] = Field(default_factory=list, max_length=3)
    review_valid_until: datetime | None = None


@router.get("/webhooks/meta/leadgen", include_in_schema=False)
async def verify_meta_leadgen_webhook(
    request: Request,
    container: ContainerDependency,
) -> Response:
    challenge = (
        container.meta_lead_webhooks.verify_challenge(
            request.query_params.get("hub.mode"),
            request.query_params.get("hub.verify_token"),
            request.query_params.get("hub.challenge"),
        )
        if container.meta_lead_webhooks is not None
        else None
    )
    return PlainTextResponse(challenge, status_code=200) if challenge is not None else Response(status_code=403)


@router.post("/webhooks/meta/leadgen", include_in_schema=False)
async def receive_meta_leadgen_webhook(request: Request, container: ContainerDependency) -> Response:
    if container.meta_lead_webhooks is None:
        return Response(status_code=503)
    try:
        await container.meta_lead_webhooks.admit(
            await request.body(),
            request.headers.get("x-hub-signature-256"),
        )
    except MetaWebhookRejected:
        return Response(status_code=403)
    return Response(status_code=200)


@router.get("/api/provider-connectors")
async def list_meta_connectors(request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        _require_capability(authentication, "providers:read")
        if container.meta_connector_management is None:
            raise RuntimeError("connector_unavailable")
        items = await container.meta_connector_management.list(_context(request, authentication))
    except Exception as error:
        return _connector_error(request, error)
    return JSONResponse(jsonable_encoder({"items": items}), headers=NO_STORE_HEADERS)


@router.post("/api/provider-connectors")
async def create_meta_connector(
    payload: MetaConnectorCreateRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _mutation_authentication(request, container)
        _require_capability(authentication, "providers:manage")
        membership = authentication.identity.active_membership
        if membership is None or container.meta_connector_management is None:
            raise RuntimeError("connector_unavailable")
        result = await container.meta_connector_management.create(
            _context(request, authentication), membership.id, **payload.model_dump()
        )
    except Exception as error:
        return _connector_error(request, error)
    return JSONResponse(jsonable_encoder(result), status_code=201, headers=NO_STORE_HEADERS)


@router.post("/api/provider-connectors/{contract_id}/submit-review")
async def submit_meta_connector(
    contract_id: UUID, payload: ConnectorVersionRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _mutation_authentication(request, container)
        _require_capability(authentication, "providers:manage")
        if container.meta_connector_management is None:
            raise RuntimeError("connector_unavailable")
        result = await container.meta_connector_management.submit(
            _context(request, authentication), contract_id, payload.version
        )
    except Exception as error:
        return _connector_error(request, error)
    return JSONResponse(jsonable_encoder(result), headers=NO_STORE_HEADERS)


@router.post("/api/provider-connectors/{contract_id}/review")
async def review_meta_connector(
    contract_id: UUID, payload: MetaConnectorReviewRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _mutation_authentication(request, container)
        _require_capability(authentication, "providers:review")
        membership = authentication.identity.active_membership
        if membership is None or container.meta_connector_management is None:
            raise RuntimeError("connector_unavailable")
        result = await container.meta_connector_management.review(
            _context(request, authentication),
            membership.id,
            contract_id,
            payload.version,
            approve=payload.approve,
            approved_permissions=payload.approved_permissions,
            review_valid_until=payload.review_valid_until,
        )
    except Exception as error:
        return _connector_error(request, error)
    return JSONResponse(jsonable_encoder(result), headers=NO_STORE_HEADERS)


@router.get("/api/provider-connectors/{contract_id}/ingestions")
async def list_meta_connector_ingestions(
    contract_id: UUID, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        _require_capability(authentication, "providers:read")
        if container.meta_connector_management is None:
            raise RuntimeError("connector_unavailable")
        items = await container.meta_connector_management.ingestions(_context(request, authentication), contract_id)
    except Exception as error:
        return _connector_error(request, error)
    return JSONResponse(jsonable_encoder({"items": items}), headers=NO_STORE_HEADERS)


@router.post("/api/provider-connectors/{contract_id}/bindings/{binding_id}/disable")
async def disable_meta_connector(
    contract_id: UUID, binding_id: UUID, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _mutation_authentication(request, container)
        _require_capability(authentication, "providers:manage")
        if container.meta_connector_management is None:
            raise RuntimeError("connector_unavailable")
        del binding_id  # A contract has one binding in the initial pilot; the service scopes the operation by contract.
        await container.meta_connector_management.disable(_context(request, authentication), contract_id)
    except Exception as error:
        return _connector_error(request, error)
    return Response(status_code=204, headers=NO_STORE_HEADERS)


async def _mutation_authentication(request: Request, container: ContainerDependency) -> RequestAuthentication:
    authentication = await required_authentication(request, container)
    require_json_content_type(request)
    require_trusted_origin(request, container.settings.cors_allowed_origins)
    require_csrf_token(request, authentication.identity.csrf_token)
    return authentication


def _context(request: Request, authentication: RequestAuthentication) -> TenantContext:
    membership = authentication.identity.active_membership
    if membership is None:
        raise AuthenticationRequired
    return TenantContext(authentication.identity.user.id, membership.organization_id, request.state.request_id)


def _require_capability(authentication: RequestAuthentication, capability: str) -> None:
    if capability not in capabilities_for(authentication.identity.user, authentication.identity.active_membership):
        raise InsufficientCapability


def _connector_error(request: Request, error: Exception) -> Response:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, (CsrfValidationFailed, InsufficientCapability)):
        return api_error(request, 403, "request_rejected", "La requête a été refusée.")
    if isinstance(error, ConnectorContractNotFound):
        return api_error(request, 404, "resource_not_found", "Connecteur introuvable.")
    if isinstance(error, ConnectorContractConflict):
        return api_error(
            request, 409, "connector_conflict", "Le contrat connecteur a changé ou ne peut pas être validé."
        )
    if isinstance(error, ValueError):
        return api_error(request, 422, "validation_failed", "La commande connecteur est invalide.")
    return api_error(request, 503, "connector_unavailable", "Le connecteur est temporairement indisponible.")
