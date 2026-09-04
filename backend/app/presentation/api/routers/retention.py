from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    AcquisitionNotApproved,
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    CsrfValidationFailed,
    IdempotencyKeyReused,
    InsufficientCapability,
    ProspectComplianceResourceNotFound,
    ProspectResourceNotFound,
    ProspectServiceUnavailable,
    ProspectVersionConflict,
    RetentionHoldAlreadyReleased,
)
from ....application.tenancy import TenantContext
from ....application.use_cases.csv_import import CsvImportPreview, CsvImportValidation
from ....domain.csv_import import CsvImportQuarantineView, CsvImportRunView, CsvImportSessionView
from ....domain.identity import capabilities_for
from ....domain.prospect import (
    ArchiveReasonCode,
    RetentionHoldReasonCode,
    RetentionHoldReleaseReasonCode,
    RetentionPolicyPatch,
    RetentionPolicyStatus,
    RetentionResourceType,
    RetentionReviewState,
)
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..mappers import (
    to_import_declaration_response,
    to_retention_hold_response,
    to_retention_policy_response,
    to_retention_review_response,
)
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import (
    ArchivedChannelResponse,
    ArchivedContactResponse,
    ArchivedProspectResponse,
    ArchiveRequest,
    CsvImportMappingRequest,
    CsvImportPreviewResponse,
    CsvImportQuarantineResponse,
    CsvImportReportResponse,
    CsvImportSessionResponse,
    CsvImportValidationResponse,
    CsvImportVersionRequest,
    ImportDeclarationCreateRequest,
    ImportDeclarationPageResponse,
    ImportDeclarationResponse,
    RetentionHoldCreateRequest,
    RetentionHoldPageResponse,
    RetentionHoldReleaseRequest,
    RetentionHoldResponse,
    RetentionPolicyCreateRequest,
    RetentionPolicyPageResponse,
    RetentionPolicyResponse,
    RetentionPolicyUpdateRequest,
    RetentionReviewPageResponse,
    VersionedCommand,
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter(tags=["retention"])
OPTIONAL_DUE_BEFORE_QUERY = Query(default=None)
OPTIONAL_RESOURCE_ID_QUERY = Query(default=None)


@router.get("/api/retention/policies", response_model=RetentionPolicyPageResponse)
async def list_retention_policies(
    request: Request,
    container: ContainerDependency,
    resource_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_retention_policies is None:
            raise ProspectServiceUnavailable
        policies = await container.list_retention_policies.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "retention:read"),
            resource_type=RetentionResourceType(resource_type) if resource_type else None,
            status=RetentionPolicyStatus(status) if status else None,
            limit=limit,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    payload = RetentionPolicyPageResponse(items=[to_retention_policy_response(item) for item in policies])
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/api/retention/policies/{policy_id}", response_model=RetentionPolicyResponse)
async def get_retention_policy(
    policy_id: UUID,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_retention_policy is None:
            raise ProspectServiceUnavailable
        policy = await container.get_retention_policy.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "retention:read"),
            policy_id=policy_id,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_retention_policy_response(policy).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/retention/policies", response_model=RetentionPolicyResponse)
async def create_retention_policy(
    payload: RetentionPolicyCreateRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.create_retention_policy is None:
            raise ProspectServiceUnavailable
        policy = await container.create_retention_policy.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "retention:manage"),
            resource_type=RetentionResourceType(payload.resource_type),
            policy_code=payload.policy_code,
            label=payload.label,
            review_after_days=payload.review_after_days,
            archive_after_days=payload.archive_after_days,
            effective_from=payload.effective_from,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        to_retention_policy_response(policy).model_dump(mode="json"), status_code=201, headers=NO_STORE_HEADERS
    )


@router.patch("/api/retention/policies/{policy_id}", response_model=RetentionPolicyResponse)
async def update_retention_policy(
    policy_id: UUID,
    payload: RetentionPolicyUpdateRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.update_retention_policy is None:
            raise ProspectServiceUnavailable
        policy = await container.update_retention_policy.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "retention:manage"),
            policy_id=policy_id,
            patch=RetentionPolicyPatch(
                version=payload.version,
                policy_code=payload.policy_code,
                label=payload.label,
                review_after_days=payload.review_after_days,
                archive_after_days=payload.archive_after_days,
                effective_from=payload.effective_from,
            ),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_retention_policy_response(policy).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/retention/policies/{policy_id}/activate", response_model=RetentionPolicyResponse)
async def activate_retention_policy(
    policy_id: UUID,
    payload: VersionedCommand,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.activate_retention_policy is None:
            raise ProspectServiceUnavailable
        policy = await container.activate_retention_policy.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "retention:manage"),
            policy_id=policy_id,
            expected_version=payload.version,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_retention_policy_response(policy).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/api/retention/reviews", response_model=RetentionReviewPageResponse)
async def list_retention_reviews(
    request: Request,
    container: ContainerDependency,
    resource_type: str | None = Query(default=None),
    review_state: str | None = Query(default=None),
    due_before: datetime | None = OPTIONAL_DUE_BEFORE_QUERY,
    limit: int = Query(default=25, ge=1, le=100),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_retention_reviews is None:
            raise ProspectServiceUnavailable
        reviews = await container.list_retention_reviews.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "retention:read"),
            resource_type=RetentionResourceType(resource_type) if resource_type else None,
            review_state=RetentionReviewState(review_state) if review_state else None,
            due_before=due_before,
            limit=limit,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    payload = RetentionReviewPageResponse(items=[to_retention_review_response(item) for item in reviews])
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/api/retention/holds", response_model=RetentionHoldPageResponse)
async def list_retention_holds(
    request: Request,
    container: ContainerDependency,
    resource_type: str | None = Query(default=None),
    resource_id: UUID | None = OPTIONAL_RESOURCE_ID_QUERY,
    active_only: bool | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_retention_holds is None:
            raise ProspectServiceUnavailable
        holds = await container.list_retention_holds.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "retention:read"),
            resource_type=RetentionResourceType(resource_type) if resource_type else None,
            resource_id=resource_id,
            active_only=active_only,
            limit=limit,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    payload = RetentionHoldPageResponse(items=[to_retention_hold_response(item, include_note=False) for item in holds])
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/api/retention/holds/{hold_id}", response_model=RetentionHoldResponse)
async def get_retention_hold(
    hold_id: UUID,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_retention_hold is None:
            raise ProspectServiceUnavailable
        hold = await container.get_retention_hold.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "retention:read"),
            hold_id=hold_id,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_retention_hold_response(hold).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/retention/holds", response_model=RetentionHoldResponse)
async def place_retention_hold(
    payload: RetentionHoldCreateRequest,
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if not idempotency_key:
            raise ValueError("Idempotency-Key est obligatoire.")
        if container.place_retention_hold is None:
            raise ProspectServiceUnavailable
        hold = await container.place_retention_hold.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "retention:hold:create"),
            resource_type=RetentionResourceType(payload.resource_type),
            resource_id=payload.resource_id,
            reason_code=RetentionHoldReasonCode(payload.reason_code),
            note=payload.note,
            idempotency_key=idempotency_key,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        to_retention_hold_response(hold).model_dump(mode="json"), status_code=201, headers=NO_STORE_HEADERS
    )


@router.post("/api/retention/holds/{hold_id}/release", response_model=RetentionHoldResponse)
async def release_retention_hold(
    hold_id: UUID,
    payload: RetentionHoldReleaseRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.release_retention_hold is None:
            raise ProspectServiceUnavailable
        hold = await container.release_retention_hold.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "retention:hold:release"),
            hold_id=hold_id,
            expected_version=payload.version,
            release_reason_code=RetentionHoldReleaseReasonCode(payload.release_reason_code),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_retention_hold_response(hold).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/api/import-declarations", response_model=ImportDeclarationPageResponse)
async def list_import_declarations(
    request: Request,
    container: ContainerDependency,
    limit: int = Query(default=25, ge=1, le=100),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.list_import_declarations is None:
            raise ProspectServiceUnavailable
        declarations = await container.list_import_declarations.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "imports:read"),
            limit=limit,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    payload = ImportDeclarationPageResponse(items=[to_import_declaration_response(item) for item in declarations])
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/import-declarations", response_model=ImportDeclarationResponse)
async def declare_import(
    payload: ImportDeclarationCreateRequest,
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if not idempotency_key:
            raise ValueError("Idempotency-Key est obligatoire.")
        if container.declare_import is None:
            raise ProspectServiceUnavailable
        declaration = await container.declare_import.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "imports:declare"),
            acquisition_record_id=payload.acquisition_record_id,
            declaration_label=payload.declaration_label,
            format_code=payload.format_code,
            schema_code=payload.schema_code,
            declared_field_codes=tuple(payload.declared_field_codes),
            declared_data_categories=tuple(payload.declared_data_categories),
            estimated_row_count=payload.estimated_row_count,
            declared_content_sha256=payload.declared_content_sha256,
            idempotency_key=idempotency_key,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        to_import_declaration_response(declaration).model_dump(mode="json"),
        status_code=201,
        headers=NO_STORE_HEADERS,
    )


@router.get("/api/import-declarations/{declaration_id}", response_model=ImportDeclarationResponse)
async def get_import_declaration(declaration_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_import_declaration is None:
            raise ProspectServiceUnavailable
        declaration = await container.get_import_declaration.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "imports:read"),
            declaration_id=declaration_id,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_import_declaration_response(declaration).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/import-declarations/{declaration_id}/cancel", response_model=ImportDeclarationResponse)
async def cancel_import_declaration(
    declaration_id: UUID,
    payload: VersionedCommand,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.cancel_import_declaration is None:
            raise ProspectServiceUnavailable
        declaration = await container.cancel_import_declaration.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "imports:declare"),
            declaration_id=declaration_id,
            expected_version=payload.version,
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_import_declaration_response(declaration).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/import-declarations/{declaration_id}/archive", response_model=ImportDeclarationResponse)
async def archive_import_declaration(
    declaration_id: UUID,
    payload: ArchiveRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.archive_import_declaration is None:
            raise ProspectServiceUnavailable
        declaration = await container.archive_import_declaration.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "imports:archive"),
            declaration_id=declaration_id,
            expected_version=payload.version,
            archive_reason_code=ArchiveReasonCode(payload.archive_reason_code),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(to_import_declaration_response(declaration).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.put("/api/import-declarations/{declaration_id}/file", response_model=CsvImportPreviewResponse)
async def upload_csv_import_file(declaration_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await _authenticated_binary_mutation(request, container)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() not in {
            "text/csv",
            "application/csv",
        }:
            raise ValueError("Le téléversement accepte uniquement text/csv.")
        if container.upload_csv_import is None:
            raise ProspectServiceUnavailable
        preview = await container.upload_csv_import.execute(
            context=_tenant_context(request, authentication),
            declaration_id=declaration_id,
            chunks=request.stream(),
            has_capability=_has_capability(authentication, "imports:declare"),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_preview_response(preview).model_dump(mode="json"), status_code=201, headers=NO_STORE_HEADERS)


@router.get("/api/csv-imports/{session_id}/preview", response_model=CsvImportPreviewResponse)
async def get_csv_import_preview(session_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_csv_import_preview is None:
            raise ProspectServiceUnavailable
        preview = await container.get_csv_import_preview.execute(
            context=_tenant_context(request, authentication),
            session_id=session_id,
            has_capability=_has_capability(authentication, "imports:read"),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_preview_response(preview).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.patch("/api/csv-imports/{session_id}/mapping", response_model=CsvImportSessionResponse)
async def map_csv_import(
    session_id: UUID, payload: CsvImportMappingRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.map_csv_import is None:
            raise ProspectServiceUnavailable
        session = await container.map_csv_import.execute(
            context=_tenant_context(request, authentication),
            session_id=session_id,
            expected_version=payload.version,
            mapping={key: str(value) for key, value in payload.mapping.items()},
            has_capability=_has_capability(authentication, "imports:declare"),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_session_response(session).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/csv-imports/{session_id}/validate", response_model=CsvImportValidationResponse)
async def validate_csv_import(
    session_id: UUID, payload: CsvImportVersionRequest, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.validate_csv_import is None:
            raise ProspectServiceUnavailable
        validation = await container.validate_csv_import.execute(
            context=_tenant_context(request, authentication),
            session_id=session_id,
            expected_version=payload.version,
            has_capability=_has_capability(authentication, "imports:declare"),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_validation_response(validation).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/csv-imports/{session_id}/confirm", response_model=CsvImportReportResponse)
async def confirm_csv_import(
    session_id: UUID,
    payload: CsvImportVersionRequest,
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.confirm_csv_import is None:
            raise ProspectServiceUnavailable
        report = await container.confirm_csv_import.execute(
            context=_tenant_context(request, authentication),
            session_id=session_id,
            expected_version=payload.version,
            idempotency_key=idempotency_key or "",
            has_capability=_has_capability(authentication, "imports:declare"),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_report_response(report).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.get("/api/csv-import-runs/{run_id}/quarantines", response_model=list[CsvImportQuarantineResponse])
async def list_csv_import_quarantines(run_id: UUID, request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.get_csv_import_report is None:
            raise ProspectServiceUnavailable
        quarantines = await container.get_csv_import_report.execute(
            context=_tenant_context(request, authentication),
            run_id=run_id,
            has_capability=_has_capability(authentication, "imports:read"),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        [_quarantine_response(item).model_dump(mode="json") for item in quarantines],
        headers=NO_STORE_HEADERS,
    )


@router.post("/api/prospects/{prospect_id}/archive", response_model=ArchivedProspectResponse)
async def archive_prospect(
    prospect_id: UUID,
    payload: ArchiveRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.archive_prospect is None:
            raise ProspectServiceUnavailable
        outcome = await container.archive_prospect.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "prospects:archive"),
            prospect_id=prospect_id,
            expected_version=payload.version,
            archive_reason_code=ArchiveReasonCode(payload.archive_reason_code),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        ArchivedProspectResponse(
            prospect_id=outcome.prospect_id,
            version=outcome.version,
            contacts_archived=outcome.contacts_archived,
            channels_archived=outcome.channels_archived,
        ).model_dump(mode="json"),
        headers=NO_STORE_HEADERS,
    )


@router.post("/api/contacts/{contact_id}/archive", response_model=ArchivedContactResponse)
async def archive_contact(
    contact_id: UUID,
    payload: ArchiveRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.archive_contact is None:
            raise ProspectServiceUnavailable
        outcome = await container.archive_contact.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "contacts:archive"),
            contact_id=contact_id,
            expected_version=payload.version,
            archive_reason_code=ArchiveReasonCode(payload.archive_reason_code),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        ArchivedContactResponse(
            contact_id=outcome.contact_id,
            version=outcome.version,
            channels_archived=outcome.channels_archived,
        ).model_dump(mode="json"),
        headers=NO_STORE_HEADERS,
    )


@router.post("/api/contact-channels/{channel_id}/archive", response_model=ArchivedChannelResponse)
async def archive_contact_channel(
    channel_id: UUID,
    payload: ArchiveRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if container.archive_contact_channel is None:
            raise ProspectServiceUnavailable
        outcome = await container.archive_contact_channel.execute(
            context=_tenant_context(request, authentication),
            has_capability=_has_capability(authentication, "contacts:archive"),
            channel_id=channel_id,
            expected_version=payload.version,
            archive_reason_code=ArchiveReasonCode(payload.archive_reason_code),
        )
    except Exception as error:
        response = _retention_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        ArchivedChannelResponse(channel_id=outcome.channel_id, version=outcome.version).model_dump(mode="json"),
        headers=NO_STORE_HEADERS,
    )


async def _authenticated_mutation(request: Request, container: ContainerDependency) -> RequestAuthentication:
    require_json_content_type(request)
    require_trusted_origin(request, container.settings.cors_allowed_origins)
    authentication = await required_authentication(request, container)
    require_csrf_token(request, authentication.identity.csrf_token)
    return authentication


async def _authenticated_binary_mutation(request: Request, container: ContainerDependency) -> RequestAuthentication:
    require_trusted_origin(request, container.settings.cors_allowed_origins)
    authentication = await required_authentication(request, container)
    require_csrf_token(request, authentication.identity.csrf_token)
    return authentication


def _session_response(session: CsvImportSessionView) -> CsvImportSessionResponse:
    return CsvImportSessionResponse(
        id=session.id,
        declaration_id=session.declaration_id,
        content_sha256=session.content_sha256,
        byte_size=session.byte_size,
        headers=list(session.headers),
        mapping=session.mapping,
        status=session.status.value,
        row_count=session.row_count,
        ready_count=session.ready_count,
        duplicate_count=session.duplicate_count,
        review_count=session.review_count,
        quarantined_count=session.quarantined_count,
        created_at=session.created_at,
        expires_at=session.expires_at,
        confirmed_at=session.confirmed_at,
        version=session.version,
    )


def _preview_response(preview: CsvImportPreview) -> CsvImportPreviewResponse:
    return CsvImportPreviewResponse(session=_session_response(preview.session), rows=list(preview.rows))


def _validation_response(validation: CsvImportValidation) -> CsvImportValidationResponse:
    return CsvImportValidationResponse(
        session=_session_response(validation.session),
        row_count=validation.row_count,
        ready_count=validation.ready_count,
        duplicate_count=validation.duplicate_count,
        review_count=validation.review_count,
        quarantined_count=validation.quarantined_count,
    )


def _report_response(report: CsvImportRunView) -> CsvImportReportResponse:
    return CsvImportReportResponse(
        id=report.id,
        session_id=report.session_id,
        created_count=report.created_count,
        duplicate_count=report.duplicate_count,
        review_count=report.review_count,
        quarantined_count=report.quarantined_count,
        completed_at=report.completed_at,
    )


def _quarantine_response(item: CsvImportQuarantineView) -> CsvImportQuarantineResponse:
    return CsvImportQuarantineResponse(
        line_number=item.line_number,
        reason_codes=list(item.reason_codes),
        opaque_reference=item.opaque_reference,
    )


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


def _retention_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "request_rejected", "La requête a été refusée.")
    if isinstance(error, InsufficientCapability):
        return api_error(request, 403, "insufficient_capability", "Autorisation conservation insuffisante.")
    if isinstance(error, IdempotencyKeyReused):
        return api_error(request, 409, "idempotency_key_reused", "La clé de requête a déjà été utilisée.")
    if isinstance(error, ProspectVersionConflict):
        return api_error(request, 409, "optimistic_lock_conflict", "La ressource a changé depuis sa lecture.")
    if isinstance(error, (ProspectResourceNotFound, ProspectComplianceResourceNotFound)):
        return api_error(request, 404, "resource_not_found", "Ressource introuvable.")
    if isinstance(error, AcquisitionNotApproved):
        return api_error(request, 409, "acquisition_not_approved", "L’acquisition n’est pas approuvée.")
    if isinstance(error, RetentionHoldAlreadyReleased):
        return api_error(request, 409, "hold_already_released", "La mise en attente est déjà libérée.")
    if isinstance(error, (AuthenticationServiceUnavailable, ProspectServiceUnavailable)):
        return api_error(request, 503, "retention_unavailable", "La conservation est temporairement indisponible.")
    if isinstance(error, ValueError):
        return api_error(request, 422, "validation_failed", "La commande conservation est invalide.")
    return None
