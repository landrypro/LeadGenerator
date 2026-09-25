from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import AuthenticationRequired, UsageReportUnavailable
from ....application.tenancy import TenantContext
from ....application.use_cases.usage import UsageOwnerNotFound, UsageValidationError
from ....domain.identity import capabilities_for
from ..dependencies import ContainerDependency, required_authentication
from ..responses import NO_STORE_HEADERS, api_error

router = APIRouter(prefix="/api/usage", tags=["usage"])


async def _identity(request: Request, container: ContainerDependency):  # type: ignore[no-untyped-def]
    authentication = await required_authentication(request, container)
    membership = authentication.identity.active_membership
    if membership is None or not membership.is_active:
        raise PermissionError
    capabilities = capabilities_for(authentication.identity.user, membership)
    context = TenantContext(
        actor_id=authentication.identity.user.id,
        organization_id=membership.organization_id,
        request_id=getattr(request.state, "request_id", "unknown"),
    )
    return authentication, membership, capabilities, context


@router.get("/report")
async def usage_report(
    request: Request,
    container: ContainerDependency,
    period: str = Query("last_30_days"),
    scope: str = Query("self"),
    group_by: str = Query("day"),
    start_on: str | None = None,
    end_on: str | None = None,
    owner_membership_id: UUID | None = None,
) -> Response:
    try:
        _, membership, capabilities, context = await _identity(request, container)
        if container.get_usage_report is None:
            raise UsageReportUnavailable
        result = await container.get_usage_report.execute(
            context=context,
            membership_id=membership.id,
            scope=scope,
            owner_membership_id=owner_membership_id,
            period=period,
            start_on=start_on,
            end_on=end_on,
            group_by=group_by,
            can_read_self="usage:read:self" in capabilities,
            can_read_organization="usage:read:organization" in capabilities,
        )
    except AuthenticationRequired:
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    except PermissionError:
        return api_error(request, 403, "usage_scope_forbidden", "Lecture de l’usage non autorisée.")
    except UsageOwnerNotFound:
        return api_error(request, 404, "usage_owner_not_found", "Membre introuvable.")
    except UsageValidationError as error:
        return api_error(request, 422, "usage_query_invalid", str(error), fields={error.field: str(error)})
    except UsageReportUnavailable:
        return api_error(request, 503, "usage_report_unavailable", "Le rapport d’usage est indisponible.")
    return JSONResponse(result, headers=NO_STORE_HEADERS)


@router.get("/current")
async def current_usage(
    request: Request,
    container: ContainerDependency,
    scope: str = Query("self"),
) -> Response:
    try:
        _, _, capabilities, context = await _identity(request, container)
        if container.get_current_usage is None:
            raise UsageReportUnavailable
        result = await container.get_current_usage.execute(
            context=context,
            scope=scope,
            can_read_self="usage:read:self" in capabilities,
            can_read_organization="usage:read:organization" in capabilities,
        )
    except AuthenticationRequired:
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    except PermissionError:
        return api_error(request, 403, "usage_scope_forbidden", "Lecture de l’usage non autorisée.")
    except UsageValidationError as error:
        return api_error(request, 422, "usage_query_invalid", str(error), fields={error.field: str(error)})
    except UsageReportUnavailable:
        return api_error(request, 503, "usage_report_unavailable", "Le quota courant est indisponible.")
    return JSONResponse(result, headers=NO_STORE_HEADERS)
