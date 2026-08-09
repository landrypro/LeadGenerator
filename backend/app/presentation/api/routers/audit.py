from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    AuditUnavailable,
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    InsufficientCapability,
    InvalidAuditCursor,
)
from ....application.tenancy import ActorContext, TenantContext
from ....application.use_cases.audit import AuditEventPage
from ....domain.identity import capabilities_for
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..mappers import to_audit_event_response
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import AuditEventPageResponse

router = APIRouter(tags=["audit"])

_ALLOWED_QUERY_KEYS = frozenset(
    {"limit", "cursor", "occurred_from", "occurred_to", "action", "entity_type", "entity_id", "actor_id"}
)
AuditLimit = Annotated[int, Query(ge=1, le=100)]
AuditCursor = Annotated[str | None, Query(max_length=1024)]
AuditDate = Annotated[datetime | None, Query()]
AuditActionCode = Annotated[str | None, Query(min_length=1, max_length=96)]
AuditEntityType = Annotated[str | None, Query(min_length=1, max_length=64)]
AuditEntityId = Annotated[UUID | None, Query()]
AuditActorId = Annotated[UUID | None, Query()]


@router.get("/api/audit-events", response_model=AuditEventPageResponse)
async def list_tenant_audit_events(
    request: Request,
    container: ContainerDependency,
    limit: AuditLimit = 50,
    cursor: AuditCursor = None,
    occurred_from: AuditDate = None,
    occurred_to: AuditDate = None,
    action: AuditActionCode = None,
    entity_type: AuditEntityType = None,
    entity_id: AuditEntityId = None,
    actor_id: AuditActorId = None,
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        invalid = _unknown_query_response(request)
        if invalid is not None:
            return invalid
        if container.list_tenant_audit_events is None:
            raise AuditUnavailable
        page = await container.list_tenant_audit_events.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "audit:read"),
            cursor=cursor,
            limit=limit,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
        )
    except Exception as error:
        response = _audit_error(request, error)
        if response is not None:
            return response
        raise
    return _page_response(page)


@router.get("/api/platform/audit-events", response_model=AuditEventPageResponse)
async def list_platform_audit_events(
    request: Request,
    container: ContainerDependency,
    limit: AuditLimit = 50,
    cursor: AuditCursor = None,
    occurred_from: AuditDate = None,
    occurred_to: AuditDate = None,
    action: AuditActionCode = None,
    entity_type: AuditEntityType = None,
    entity_id: AuditEntityId = None,
    actor_id: AuditActorId = None,
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        invalid = _unknown_query_response(request)
        if invalid is not None:
            return invalid
        if container.list_platform_audit_events is None:
            raise AuditUnavailable
        page = await container.list_platform_audit_events.execute(
            context=ActorContext(
                actor_id=authentication.identity.user.id,
                request_id=getattr(request.state, "request_id", "unknown"),
            ),
            has_capability=_has_capability(authentication, "platform:audit:read"),
            cursor=cursor,
            limit=limit,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
        )
    except Exception as error:
        response = _audit_error(request, error)
        if response is not None:
            return response
        raise
    return _page_response(page)


def _page_response(page: AuditEventPage) -> JSONResponse:
    payload = AuditEventPageResponse(
        items=[to_audit_event_response(item) for item in page.items],
        next_cursor=page.next_cursor,
        occurred_from=page.occurred_from,
        occurred_to=page.occurred_to,
    )
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


def _tenant_context(request: Request, authentication: RequestAuthentication) -> TenantContext:
    membership = authentication.identity.active_membership
    if membership is None:
        raise InsufficientCapability
    return TenantContext(
        actor_id=authentication.identity.user.id,
        organization_id=membership.organization_id,
        request_id=getattr(request.state, "request_id", "unknown"),
    )


def _has_capability(authentication: RequestAuthentication, capability: str) -> bool:
    return capability in capabilities_for(authentication.identity.user, authentication.identity.active_membership)


def _unknown_query_response(request: Request) -> Response | None:
    unknown = sorted(set(request.query_params) - _ALLOWED_QUERY_KEYS)
    if not unknown:
        return None
    return api_error(
        request,
        422,
        "validation_failed",
        "Les filtres d’audit sont invalides.",
        fields={key: "Paramètre interdit." for key in unknown},
    )


def _audit_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, InsufficientCapability):
        return api_error(request, 403, "insufficient_capability", "Autorisation d’audit insuffisante.")
    if isinstance(error, InvalidAuditCursor):
        return api_error(request, 422, "invalid_cursor", "Le curseur d’audit est invalide.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "validation_failed", "Les filtres d’audit sont invalides.")
    if isinstance(error, (AuthenticationServiceUnavailable, AuditUnavailable)):
        return api_error(request, 503, "audit_unavailable", "Le journal d’audit est temporairement indisponible.")
    return None
