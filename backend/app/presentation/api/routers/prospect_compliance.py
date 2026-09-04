from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    AcquisitionNotApproved,
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    ChannelDuplicate,
    CsrfValidationFailed,
    IdempotencyKeyReused,
    InsufficientCapability,
    InvalidPermissionTransition,
    ProspectComplianceResourceNotFound,
    ProspectResourceNotFound,
    ProspectServiceUnavailable,
    ProspectVersionConflict,
)
from ....application.tenancy import TenantContext
from ....application.use_cases import AcquisitionSourceCommand, ManualSourceCommand, SourceCommand
from ....domain.identity import capabilities_for
from ....domain.prospect import (
    ContactChannelType,
    ContactPermissionStatus,
    ProvenanceSourceKind,
    SourceProviderPatch,
    SourceProviderStatus,
)
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..mappers import (
    to_acquisition_response,
    to_contact_channel_response,
    to_contact_permission_response,
    to_contact_response,
    to_source_provider_response,
)
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import (
    AcquisitionDecisionRequest,
    AcquisitionDeclareRequest,
    AcquisitionRecordPageResponse,
    AcquisitionRecordResponse,
    AcquisitionSourceRequest,
    ContactChannelCreateRequest,
    ContactChannelResponse,
    ContactCreateRequest,
    ContactPageResponse,
    ContactPermissionResponse,
    ContactPermissionUpdateRequest,
    ContactResponse,
    ManualSourceRequest,
    SourceProviderCreateRequest,
    SourceProviderPageResponse,
    SourceProviderResponse,
    SourceProviderUpdateRequest,
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(tags=["prospect-compliance"])


@router.get("/api/source-providers", response_model=SourceProviderPageResponse)
async def list_source_providers(
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_source_providers is None:
            raise ProspectServiceUnavailable
        providers = await container.list_source_providers.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "providers:read"),
            limit=limit,
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    payload = SourceProviderPageResponse(items=[to_source_provider_response(item) for item in providers])
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/source-providers", response_model=SourceProviderResponse)
async def create_source_provider(
    payload: SourceProviderCreateRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.create_source_provider is None:
            raise ProspectServiceUnavailable
        provider = await container.create_source_provider.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "providers:manage"),
            source_kind=ProvenanceSourceKind(payload.source_kind),
            label=payload.label,
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        to_source_provider_response(provider).model_dump(mode="json"), status_code=201, headers=NO_STORE_HEADERS
    )


@router.get("/api/source-providers/{provider_id}", response_model=SourceProviderResponse)
async def get_source_provider(provider_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_source_provider is None:
            raise ProspectServiceUnavailable
        provider = await container.get_source_provider.execute(
            context=_tenant_context(request, authentication),
            provider_id=provider_id,
            has_capability=_has_capability(authentication, "providers:read"),
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_source_provider_response(provider).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.patch("/api/source-providers/{provider_id}", response_model=SourceProviderResponse)
async def update_source_provider(
    provider_id: UUID,
    payload: SourceProviderUpdateRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.update_source_provider is None:
            raise ProspectServiceUnavailable
        provider = await container.update_source_provider.execute(
            context=_tenant_context(request, authentication),
            provider_id=provider_id,
            has_capability=_has_capability(authentication, "providers:manage"),
            patch=SourceProviderPatch(
                version=payload.version,
                label=payload.label,
                status=SourceProviderStatus(payload.status) if payload.status else None,
                terms_reference=payload.terms_reference,
                terms_url=payload.terms_url,
                valid_from=payload.valid_from,
                valid_until=payload.valid_until,
                allowed_territories=tuple(payload.allowed_territories) if payload.allowed_territories else None,
                allowed_purposes=tuple(payload.allowed_purposes) if payload.allowed_purposes else None,
                allowed_data_categories=tuple(payload.allowed_data_categories)
                if payload.allowed_data_categories
                else None,
                rights_attested=payload.rights_attested,
            ),
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_source_provider_response(provider).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/acquisitions", response_model=AcquisitionRecordResponse)
async def declare_acquisition(
    payload: AcquisitionDeclareRequest,
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.declare_acquisition is None:
            raise ProspectServiceUnavailable
        acquisition = await container.declare_acquisition.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "acquisitions:declare"),
            source_kind=ProvenanceSourceKind(payload.source_kind),
            source_label=payload.source_label,
            provider_id=payload.provider_id,
            purpose=payload.purpose,
            territory=payload.territory,
            obtained_at=payload.obtained_at,
            data_categories=tuple(payload.data_categories),
            external_reference=payload.external_reference,
            idempotency_key=idempotency_key,
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        to_acquisition_response(acquisition).model_dump(mode="json"), status_code=201, headers=NO_STORE_HEADERS
    )


@router.get("/api/acquisitions", response_model=AcquisitionRecordPageResponse)
async def list_acquisitions(
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_acquisitions is None:
            raise ProspectServiceUnavailable
        acquisitions = await container.list_acquisitions.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "compliance:read"),
            limit=limit,
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    payload = AcquisitionRecordPageResponse(items=[to_acquisition_response(item) for item in acquisitions])
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/api/acquisitions/{acquisition_id}", response_model=AcquisitionRecordResponse)
async def get_acquisition(acquisition_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_acquisition is None:
            raise ProspectServiceUnavailable
        acquisition = await container.get_acquisition.execute(
            context=_tenant_context(request, authentication),
            acquisition_id=acquisition_id,
            has_capability=_has_capability(authentication, "compliance:read"),
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_acquisition_response(acquisition).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/acquisitions/{acquisition_id}/decision", response_model=AcquisitionRecordResponse)
async def decide_acquisition(
    acquisition_id: UUID,
    payload: AcquisitionDecisionRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.decide_acquisition is None:
            raise ProspectServiceUnavailable
        acquisition = await container.decide_acquisition.execute(
            context=_tenant_context(request, authentication),
            acquisition_id=acquisition_id,
            expected_version=payload.version,
            approve=payload.decision == "approve",
            reason_code=payload.reason_code,
            has_capability=_has_capability(authentication, "acquisitions:review"),
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_acquisition_response(acquisition).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/prospects/{prospect_id}/contacts", response_model=ContactResponse)
async def create_contact(
    prospect_id: UUID,
    payload: ContactCreateRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.create_contact is None:
            raise ProspectServiceUnavailable
        contact = await container.create_contact.execute(
            context=_tenant_context(request, authentication),
            prospect_id=prospect_id,
            display_name=payload.display_name,
            role_label=payload.role_label,
            source=_source_command(payload.source),
            has_capability=_has_capability(authentication, "contacts:write"),
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_contact_response(contact).model_dump(mode="json"), status_code=201, headers=NO_STORE_HEADERS)


@router.get("/api/prospects/{prospect_id}/contacts", response_model=ContactPageResponse)
async def list_contacts(prospect_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_contacts is None:
            raise ProspectServiceUnavailable
        contacts = await container.list_contacts.execute(
            context=_tenant_context(request, authentication),
            prospect_id=prospect_id,
            has_capability=_has_capability(authentication, "contacts:read"),
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    payload = ContactPageResponse(items=[to_contact_response(item) for item in contacts])
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/api/prospects/{prospect_id}/channels", response_model=list[ContactChannelResponse])
async def list_prospect_channels(prospect_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_prospect_channels is None:
            raise ProspectServiceUnavailable
        items = await container.list_prospect_channels.execute(
            context=_tenant_context(request, authentication),
            prospect_id=prospect_id,
            has_capability=_has_capability(authentication, "contacts:read"),
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        [to_contact_channel_response(item).model_dump(mode="json") for item in items], headers=NO_STORE_HEADERS
    )


@router.get("/api/contacts/{contact_id}/channels", response_model=list[ContactChannelResponse])
async def list_contact_channels(contact_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_contact_channels is None:
            raise ProspectServiceUnavailable
        items = await container.list_contact_channels.execute(
            context=_tenant_context(request, authentication),
            contact_id=contact_id,
            has_capability=_has_capability(authentication, "contacts:read"),
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        [to_contact_channel_response(item).model_dump(mode="json") for item in items], headers=NO_STORE_HEADERS
    )


@router.post("/api/contact-channels", response_model=ContactChannelResponse)
async def create_contact_channel(
    payload: ContactChannelCreateRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.create_contact_channel is None:
            raise ProspectServiceUnavailable
        channel = await container.create_contact_channel.execute(
            context=_tenant_context(request, authentication),
            channel_type=ContactChannelType(payload.channel_type),
            value=payload.value,
            prospect_id=payload.prospect_id,
            contact_id=payload.contact_id,
            source=_source_command(payload.source),
            has_capability=_has_capability(authentication, "contacts:write"),
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        to_contact_channel_response(channel).model_dump(mode="json"), status_code=201, headers=NO_STORE_HEADERS
    )


@router.get("/api/contact-channels/{channel_id}/permission", response_model=ContactPermissionResponse)
async def get_contact_permission(channel_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_contact_permission is None:
            raise ProspectServiceUnavailable
        permission = await container.get_contact_permission.execute(
            context=_tenant_context(request, authentication),
            channel_id=channel_id,
            has_capability=_has_capability(authentication, "contacts:read"),
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_contact_permission_response(permission).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.patch("/api/contact-channels/{channel_id}/permission", response_model=ContactPermissionResponse)
async def update_contact_permission(
    channel_id: UUID,
    payload: ContactPermissionUpdateRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.change_contact_permission is None:
            raise ProspectServiceUnavailable
        outcome = await container.change_contact_permission.execute(
            context=_tenant_context(request, authentication),
            channel_id=channel_id,
            expected_version=payload.version,
            status=ContactPermissionStatus(payload.status),
            legal_basis_code=payload.legal_basis_code,
            provenance_id=payload.provenance_id,
            reason=payload.reason,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            has_restrict_capability=_has_capability(authentication, "permissions:restrict"),
            has_allow_capability=_has_capability(authentication, "permissions:allow"),
        )
    except Exception as error:
        response = _compliance_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        to_contact_permission_response(outcome.permission).model_dump(mode="json"), headers=NO_STORE_HEADERS
    )


async def _authenticated_mutation(request: Request, container: ContainerDependency) -> RequestAuthentication:
    require_json_content_type(request)
    require_trusted_origin(request, container.settings.cors_allowed_origins)
    authentication = await required_authentication(request, container)
    require_csrf_token(request, authentication.identity.csrf_token)
    return authentication


def _tenant_context(request: Request, authentication: RequestAuthentication) -> TenantContext:
    membership = authentication.identity.active_membership
    if membership is None or not membership.is_active:
        raise InsufficientCapability
    return TenantContext(
        actor_id=authentication.identity.user.id,
        organization_id=membership.organization_id,
        request_id=getattr(request.state, "request_id", "unknown"),
    )


def _has_capability(authentication: RequestAuthentication, capability: str) -> bool:
    return capability in capabilities_for(authentication.identity.user, authentication.identity.active_membership)


def _source_command(payload: ManualSourceRequest | AcquisitionSourceRequest) -> SourceCommand:
    if payload.kind == "manual":
        return ManualSourceCommand(purpose=payload.purpose, territory=payload.territory)
    return AcquisitionSourceCommand(acquisition_id=payload.acquisition_id)


def _compliance_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "request_rejected", "La requête a été refusée.")
    if isinstance(error, InsufficientCapability):
        return api_error(request, 403, "insufficient_capability", "Autorisation conformité insuffisante.")
    if isinstance(error, IdempotencyKeyReused):
        return api_error(request, 409, "idempotency_key_reused", "La clé de requête a déjà été utilisée.")
    if isinstance(error, ChannelDuplicate):
        return api_error(request, 409, "channel_duplicate", "Ce canal existe déjà pour cette cible.")
    if isinstance(error, ProspectVersionConflict):
        return api_error(request, 409, "optimistic_lock_conflict", "La ressource a changé depuis sa lecture.")
    if isinstance(error, (ProspectResourceNotFound, ProspectComplianceResourceNotFound)):
        return api_error(request, 404, "resource_not_found", "Ressource introuvable.")
    if isinstance(error, AcquisitionNotApproved):
        return api_error(request, 409, "acquisition_not_approved", "L’acquisition n’est pas approuvée.")
    if isinstance(error, InvalidPermissionTransition):
        return api_error(request, 422, "invalid_permission_transition", "La transition de permission est invalide.")
    if isinstance(error, (AuthenticationServiceUnavailable, ProspectServiceUnavailable)):
        return api_error(request, 503, "prospects_unavailable", "Les prospects sont temporairement indisponibles.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "validation_failed", "La commande conformité est invalide.")
    return None
