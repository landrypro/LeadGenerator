from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import AuthenticationRequired, AuthenticationServiceUnavailable
from ....application.tenancy import TenantContext
from ....application.use_cases.dashboard import DashboardOwnerNotFound, DashboardValidationError
from ....domain.identity import capabilities_for
from ..dependencies import ContainerDependency, required_authentication
from ..responses import NO_STORE_HEADERS, api_error

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(
    request: Request,
    container: ContainerDependency,
    scope: str = Query(...),
    period: str | None = None,
    start_on: str | None = None,
    end_on: str | None = None,
    owner_membership_id: UUID | None = None,
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        membership = authentication.identity.active_membership
        if membership is None or not membership.is_active:
            raise PermissionError
        if container.get_dashboard_summary is None:
            raise AuthenticationServiceUnavailable
        capabilities = capabilities_for(authentication.identity.user, membership)
        result = await container.get_dashboard_summary.execute(
            context=TenantContext(
                actor_id=authentication.identity.user.id,
                organization_id=membership.organization_id,
                request_id=getattr(request.state, "request_id", "unknown"),
            ),
            membership_id=membership.id,
            timezone=membership.organization_timezone,
            scope=scope,
            owner_membership_id=owner_membership_id,
            period=period,
            start_on=start_on,
            end_on=end_on,
            can_read_self="dashboard:read:self" in capabilities,
            can_read_organization="dashboard:read:organization" in capabilities,
        )
    except AuthenticationRequired:
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    except PermissionError:
        return api_error(request, 403, "dashboard_read_forbidden", "Lecture du tableau de bord non autorisée.")
    except DashboardOwnerNotFound:
        return api_error(request, 404, "dashboard_owner_not_found", "Responsable introuvable.")
    except DashboardValidationError as error:
        return api_error(request, 422, "dashboard_query_invalid", str(error), fields={error.field: str(error)})
    except AuthenticationServiceUnavailable:
        return api_error(request, 503, "dashboard_unavailable", "Le tableau de bord est indisponible.")
    return JSONResponse(result, headers=NO_STORE_HEADERS)
