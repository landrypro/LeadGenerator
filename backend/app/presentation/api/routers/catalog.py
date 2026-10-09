"""API interne P52-07 : mutations plateforme et vue tenant minimale du catalogue."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ....application.errors import (
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    CatalogApprovalRequired,
    CatalogConcurrentUpdate,
    CatalogInvalidContract,
    CatalogInvalidTransition,
    CatalogResourceConflict,
    CatalogResourceNotFound,
    CatalogSafetyCeilingExceeded,
    CatalogServiceUnavailable,
    CsrfValidationFailed,
    InsufficientCapability,
)
from ....application.ports.catalog import CatalogPlanVersionView, OrganizationPlanContractView, PlanContractOverrideView
from ....application.tenancy import ActorContext, TenantContext
from ....application.use_cases.catalog import (
    AttachOrganizationPlanContractCommand,
    CatalogAdministrationUseCases,
    CreateCatalogPlanCommand,
    CreateCatalogPlanVersionCommand,
    ProposePlanContractOverrideCommand,
)
from ....container import AppContainer
from ....domain.catalog import ContractState, CurrencyCode, EntitlementKey, EntitlementKind, EntitlementValue, PlanCode
from ....domain.identity import capabilities_for
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import (
    AttachOrganizationPlanContractRequest,
    CatalogContractOverrideResponse,
    CatalogEntitlementRequest,
    CatalogPlanResponse,
    CatalogPlanVersionResponse,
    ChangeCatalogContractStateRequest,
    CreateCatalogPlanRequest,
    CreateCatalogPlanVersionRequest,
    EntitlementProvenanceResponse,
    OrganizationCatalogResponse,
    OrganizationEntitlementResponse,
    OrganizationPlanContractResponse,
    ProposeCatalogContractOverrideRequest,
    VersionedCatalogCommand,
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(tags=["catalog"])


@router.get("/api/organization/catalog", response_model=OrganizationCatalogResponse)
async def get_current_organization_catalog(request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_organization_catalog is None:
            raise CatalogServiceUnavailable
        view = await container.get_organization_catalog.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "organization:read"),
        )
    except Exception as error:
        response = _catalog_error(request, error)
        if response is not None:
            return response
        raise
    contract = None
    if view.contract is not None:
        contract = OrganizationPlanContractResponse(
            id=view.contract.id,
            state=view.contract.state.value,
            currency=view.contract.currency.value,
            effective_from=view.contract.effective_from,
            effective_until=view.contract.effective_until,
            version=view.contract.version,
        )
    payload = OrganizationCatalogResponse(
        contract=contract,
        entitlements=[
            OrganizationEntitlementResponse(
                key=item.key.value,
                code=item.code,
                value_kind=item.value_kind.value if item.value_kind is not None else None,
                integer_value=item.integer_value,
                boolean_value=item.boolean_value,
                source=item.source,
                reason=item.reason,
                provenance=[
                    EntitlementProvenanceResponse(source=source, applied=applied) for source, applied in item.provenance
                ],
            )
            for item in view.entitlements
        ],
    )
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/platform/catalog/plans", response_model=CatalogPlanResponse)
async def create_plan(payload: CreateCatalogPlanRequest, request: Request, container: ContainerDependency) -> Response:
    async def execute(authentication: RequestAuthentication) -> CatalogPlanResponse:
        service = _catalog_administration(container)
        view = await service.create_plan(
            context=_actor_context(request, authentication),
            command=CreateCatalogPlanCommand(PlanCode(payload.code), payload.display_order, payload.operation_id),
            has_platform_capability=_has_capability(authentication, "platform:catalog:manage"),
        )
        return CatalogPlanResponse(
            id=view.id, code=view.code.value, state=view.state, display_order=view.display_order, version=view.version
        )

    return await _platform_mutation(request, container, execute)


@router.post("/api/platform/catalog/plan-versions", response_model=CatalogPlanVersionResponse)
async def create_plan_version(
    payload: CreateCatalogPlanVersionRequest, request: Request, container: ContainerDependency
) -> Response:
    async def execute(authentication: RequestAuthentication) -> CatalogPlanVersionResponse:
        service = _catalog_administration(container)
        view = await service.create_plan_version(
            context=_actor_context(request, authentication),
            command=CreateCatalogPlanVersionCommand(
                plan_id=payload.plan_id,
                version_number=payload.version_number,
                currency=CurrencyCode(payload.currency),
                billing_cycle=payload.billing_cycle,
                amount_excluding_tax_minor=payload.amount_excluding_tax_minor,
                effective_from=payload.effective_from,
                effective_until=payload.effective_until,
                entitlements=tuple(_entitlement(item) for item in payload.entitlements),
                operation_id=payload.operation_id,
            ),
            has_platform_capability=_has_capability(authentication, "platform:catalog:manage"),
        )
        return _plan_version_response(view)

    return await _platform_mutation(request, container, execute)


@router.post("/api/platform/catalog/plan-versions/{version_id}/publish", response_model=CatalogPlanVersionResponse)
async def publish_plan_version(
    version_id: UUID, payload: VersionedCatalogCommand, request: Request, container: ContainerDependency
) -> Response:
    async def execute(authentication: RequestAuthentication) -> CatalogPlanVersionResponse:
        view = await _catalog_administration(container).publish_plan_version(
            context=_actor_context(request, authentication),
            version_id=version_id,
            expected_version=payload.version,
            operation_id=payload.operation_id,
            has_platform_capability=_has_capability(authentication, "platform:catalog:manage"),
        )
        return _plan_version_response(view)

    return await _platform_mutation(request, container, execute)


@router.post("/api/platform/catalog/contracts", response_model=OrganizationPlanContractResponse)
async def attach_organization_contract(
    payload: AttachOrganizationPlanContractRequest, request: Request, container: ContainerDependency
) -> Response:
    async def execute(authentication: RequestAuthentication) -> OrganizationPlanContractResponse:
        view = await _catalog_administration(container).attach_organization_contract(
            context=_actor_context(request, authentication),
            command=AttachOrganizationPlanContractCommand(
                organization_id=payload.organization_id,
                plan_version_id=payload.plan_version_id,
                state=ContractState(payload.state),
                effective_from=payload.effective_from,
                effective_until=payload.effective_until,
                operation_id=payload.operation_id,
            ),
            has_platform_capability=_has_capability(authentication, "platform:catalog:manage"),
        )
        return _contract_response(view)

    return await _platform_mutation(request, container, execute)


@router.post("/api/platform/catalog/contracts/{contract_id}/state", response_model=OrganizationPlanContractResponse)
async def change_contract_state(
    contract_id: UUID, payload: ChangeCatalogContractStateRequest, request: Request, container: ContainerDependency
) -> Response:
    async def execute(authentication: RequestAuthentication) -> OrganizationPlanContractResponse:
        view = await _catalog_administration(container).change_contract_state(
            context=_actor_context(request, authentication),
            contract_id=contract_id,
            expected_version=payload.version,
            state=ContractState(payload.state),
            operation_id=payload.operation_id,
            has_platform_capability=_has_capability(authentication, "platform:catalog:manage"),
        )
        return _contract_response(view)

    return await _platform_mutation(request, container, execute)


@router.post("/api/platform/catalog/overrides", response_model=CatalogContractOverrideResponse)
async def propose_contract_override(
    payload: ProposeCatalogContractOverrideRequest, request: Request, container: ContainerDependency
) -> Response:
    async def execute(authentication: RequestAuthentication) -> CatalogContractOverrideResponse:
        view = await _catalog_administration(container).propose_contract_override(
            context=_actor_context(request, authentication),
            command=ProposePlanContractOverrideCommand(
                contract_id=payload.contract_id,
                value=_entitlement(payload),
                justification=payload.justification,
                starts_at=payload.starts_at,
                ends_at=payload.ends_at,
                operation_id=payload.operation_id,
            ),
            has_platform_capability=_has_capability(authentication, "platform:catalog:manage"),
        )
        return _override_response(view)

    return await _platform_mutation(request, container, execute)


@router.post("/api/platform/catalog/overrides/{override_id}/approve", response_model=CatalogContractOverrideResponse)
async def approve_contract_override(
    override_id: UUID, payload: VersionedCatalogCommand, request: Request, container: ContainerDependency
) -> Response:
    async def execute(authentication: RequestAuthentication) -> CatalogContractOverrideResponse:
        view = await _catalog_administration(container).approve_contract_override(
            context=_actor_context(request, authentication),
            override_id=override_id,
            expected_version=payload.version,
            operation_id=payload.operation_id,
            has_platform_capability=_has_capability(authentication, "platform:catalog:manage"),
        )
        return _override_response(view)

    return await _platform_mutation(request, container, execute)


@router.post("/api/platform/catalog/overrides/{override_id}/revoke", response_model=CatalogContractOverrideResponse)
async def revoke_contract_override(
    override_id: UUID, payload: VersionedCatalogCommand, request: Request, container: ContainerDependency
) -> Response:
    async def execute(authentication: RequestAuthentication) -> CatalogContractOverrideResponse:
        view = await _catalog_administration(container).revoke_contract_override(
            context=_actor_context(request, authentication),
            override_id=override_id,
            expected_version=payload.version,
            operation_id=payload.operation_id,
            has_platform_capability=_has_capability(authentication, "platform:catalog:manage"),
        )
        return _override_response(view)

    return await _platform_mutation(request, container, execute)


async def _platform_mutation(
    request: Request,
    container: ContainerDependency,
    execute: Callable[[RequestAuthentication], Awaitable[BaseModel]],
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        payload = await execute(authentication)
    except Exception as error:
        response = _catalog_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


def _catalog_administration(container: AppContainer) -> CatalogAdministrationUseCases:
    service = container.catalog_administration
    if service is None:
        raise CatalogServiceUnavailable
    return service


async def _authenticated_mutation(request: Request, container: ContainerDependency) -> RequestAuthentication:
    require_json_content_type(request)
    require_trusted_origin(request, container.settings.cors_allowed_origins)
    authentication = await required_authentication(request, container)
    require_csrf_token(request, authentication.identity.csrf_token)
    return authentication


def _tenant_context(request: Request, authentication: RequestAuthentication) -> TenantContext:
    membership = authentication.identity.active_membership
    if membership is None:
        raise InsufficientCapability
    return TenantContext(
        actor_id=authentication.identity.user.id,
        organization_id=membership.organization_id,
        request_id=getattr(request.state, "request_id", "unknown"),
    )


def _actor_context(request: Request, authentication: RequestAuthentication) -> ActorContext:
    return ActorContext(authentication.identity.user.id, getattr(request.state, "request_id", "unknown"))


def _has_capability(authentication: RequestAuthentication, capability: str) -> bool:
    return capability in capabilities_for(authentication.identity.user, authentication.identity.active_membership)


def _entitlement(payload: CatalogEntitlementRequest) -> EntitlementValue:
    return EntitlementValue(
        EntitlementKey(payload.key),
        EntitlementKind(payload.value_kind),
        integer_value=payload.integer_value,
        boolean_value=payload.boolean_value,
    )


def _plan_version_response(view: CatalogPlanVersionView) -> CatalogPlanVersionResponse:
    return CatalogPlanVersionResponse(
        id=view.id,
        plan_id=view.plan_id,
        version_number=view.version_number,
        state=view.state,
        currency=view.currency.value,
        billing_cycle=view.billing_cycle,
        effective_from=view.effective_from,
        effective_until=view.effective_until,
        version=view.version,
    )


def _contract_response(view: OrganizationPlanContractView) -> OrganizationPlanContractResponse:
    return OrganizationPlanContractResponse(
        id=view.id,
        state=view.state.value,
        currency=view.currency.value,
        effective_from=view.effective_from,
        effective_until=view.effective_until,
        version=view.version,
    )


def _override_response(view: PlanContractOverrideView) -> CatalogContractOverrideResponse:
    return CatalogContractOverrideResponse(
        id=view.id,
        contract_id=view.contract_id,
        entitlement_key=view.entitlement_key.value,
        value_kind=view.value_kind.value,
        integer_value=view.integer_value,
        boolean_value=view.boolean_value,
        state=view.state.value,
        starts_at=view.starts_at,
        ends_at=view.ends_at,
        version=view.version,
    )


def _catalog_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "request_rejected", "La requête a été refusée.")
    if isinstance(error, InsufficientCapability):
        return api_error(request, 403, "insufficient_capability", "Autorisation insuffisante.")
    if isinstance(error, CatalogResourceNotFound):
        return api_error(request, 404, "catalog_resource_not_found", "Ressource catalogue introuvable.")
    if isinstance(error, CatalogResourceConflict):
        return api_error(request, 409, "catalog_resource_conflict", "Ressource commerciale concurrente.")
    if isinstance(error, CatalogConcurrentUpdate):
        fields = {"version": str(error.current_version)} if error.current_version is not None else {}
        return api_error(
            request, 409, "catalog_version_conflict", "La ressource commerciale a été modifiée.", fields=fields
        )
    if isinstance(error, CatalogInvalidTransition):
        return api_error(request, 422, "catalog_invalid_transition", "La transition commerciale est invalide.")
    if isinstance(error, CatalogApprovalRequired):
        return api_error(request, 422, "catalog_approval_required", "Un approbateur distinct est requis.")
    if isinstance(error, CatalogInvalidContract):
        return api_error(request, 422, "catalog_invalid_contract", "Le contrat ne permet pas cette opération.")
    if isinstance(error, CatalogSafetyCeilingExceeded):
        return api_error(request, 422, "safety_ceiling_exceeded", "Le plafond de sûreté est dépassé.")
    if isinstance(error, (AuthenticationServiceUnavailable, CatalogServiceUnavailable)):
        return api_error(request, 503, "catalog_unavailable", "Le catalogue est temporairement indisponible.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "validation_failed", "La commande catalogue est invalide.")
    return None
