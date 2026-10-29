"""API Billing interne P53-06 et admission publique des webhooks simulés."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse, Response

from ....application.errors import (
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    BillingOperationError,
    CatalogServiceUnavailable,
    CsrfValidationFailed,
    InsufficientCapability,
    ManualBillingGrantUnavailable,
    ProvisioningResourceNotFound,
)
from ....application.ports.billing import BillingReturnTarget, BillingWebhookAdmissionCode
from ....application.ports.manual_billing_grants import ManualBillingGrantView
from ....application.tenancy import ActorContext, TenantContext
from ....application.use_cases.billing_reconciliation import ReconciliationReason
from ....application.use_cases.manual_billing_grants import ProposeManualBillingGrantCommand
from ....domain.billing import BillingErrorCode, ManualBillingGrantReasonCode
from ....domain.identity import capabilities_for
from ....infrastructure.billing.webhooks import MAX_WEBHOOK_BODY_BYTES
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import (
    BillingCheckoutOptionResponse,
    BillingCheckoutOptionsResponse,
    BillingCheckoutSessionRequest,
    BillingPortalSessionRequest,
    BillingReconciliationRequest,
    BillingReconciliationResponse,
    BillingRefundRequest,
    BillingRefundResponse,
    BillingSessionResponse,
    BillingStateResponse,
    PlatformBillingDetailResponse,
    PlatformBillingEventResponse,
    PlatformBillingInterventionResponse,
    PlatformBillingOrganizationPageResponse,
    PlatformBillingOrganizationResponse,
    PlatformManualBillingGrantOptionResponse,
    PlatformManualBillingGrantResponse,
    ProposePlatformManualBillingGrantRequest,
    VersionedPlatformManualBillingGrantRequest,
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter()


@router.get("/api/platform/billing/organizations", response_model=PlatformBillingOrganizationPageResponse)
async def list_platform_billing_organizations(
    request: Request,
    container: ContainerDependency,
    cursor: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=25, ge=1, le=100),
    state: str | None = Query(default=None, max_length=32),
    source: str | None = Query(default=None, max_length=32),
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.platform_billing_consultation is None:
            raise CatalogServiceUnavailable
        page = await container.platform_billing_consultation.list(
            context=ActorContext(authentication.identity.user.id, getattr(request.state, "request_id", "unknown")),
            has_platform_capability="platform:billing:manage"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
            cursor=cursor,
            limit=limit,
            state=state,
            source=source,
        )
    except Exception as error:
        response = _platform_billing_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        PlatformBillingOrganizationPageResponse(
            items=[_platform_billing_organization(item) for item in page.items], next_cursor=page.next_cursor
        ).model_dump(mode="json"),
        headers=NO_STORE_HEADERS,
    )


@router.get("/api/platform/billing/organizations/{organization_id}", response_model=PlatformBillingDetailResponse)
async def get_platform_billing_organization(
    organization_id: UUID, request: Request, container: ContainerDependency
) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.platform_billing_consultation is None:
            raise CatalogServiceUnavailable
        detail = await container.platform_billing_consultation.get(
            context=ActorContext(authentication.identity.user.id, getattr(request.state, "request_id", "unknown")),
            has_platform_capability="platform:billing:manage"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
            organization_id=organization_id,
        )
    except Exception as error:
        response = _platform_billing_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        PlatformBillingDetailResponse(
            organization=_platform_billing_organization(detail.organization),
            events=[
                PlatformBillingEventResponse(event_type=item.event_type, occurred_at=item.occurred_at)
                for item in detail.events
            ],
            interventions=[
                PlatformBillingInterventionResponse(
                    kind=item.kind, status=item.status, created_at=item.created_at, updated_at=item.updated_at
                )
                for item in detail.interventions
            ],
            manual_grant=_platform_manual_billing_grant(detail.manual_grant) if detail.manual_grant else None,
        ).model_dump(mode="json"),
        headers=NO_STORE_HEADERS,
    )


@router.get(
    "/api/platform/billing/manual-grant-options",
    response_model=list[PlatformManualBillingGrantOptionResponse],
)
async def list_platform_manual_billing_grant_options(request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if container.platform_billing_consultation is None:
            raise CatalogServiceUnavailable
        if container.manual_billing_grants is None:
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        options = await container.platform_billing_consultation.list_manual_grant_options(
            context=ActorContext(authentication.identity.user.id, getattr(request.state, "request_id", "unknown")),
            has_platform_capability="platform:billing:manage"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
        )
    except Exception as error:
        response = _platform_billing_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        [
            PlatformManualBillingGrantOptionResponse(
                plan_version_id=item.plan_version_id,
                code=item.code,
                version_number=item.version_number,
                currency=item.currency,
                amount_minor=item.amount_minor,
            ).model_dump(mode="json")
            for item in options
        ],
        headers=NO_STORE_HEADERS,
    )


@router.post("/api/platform/billing/manual-grants", response_model=PlatformManualBillingGrantResponse)
async def propose_platform_manual_billing_grant(
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if idempotency_key is None:
            raise ValueError("Idempotency-Key est obligatoire.")
        payload = ProposePlatformManualBillingGrantRequest.model_validate(await request.json())
        if container.manual_billing_grants is None:
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        grant = await container.manual_billing_grants.propose(
            context=ActorContext(authentication.identity.user.id, getattr(request.state, "request_id", "unknown")),
            command=ProposeManualBillingGrantCommand(
                organization_id=payload.organization_id,
                plan_version_id=payload.plan_version_id,
                reason_code=ManualBillingGrantReasonCode(payload.reason_code),
                duration_days=payload.duration_days,
            ),
            idempotency_key=idempotency_key,
            has_platform_capability="platform:billing:manage"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
            session_issued_at=authentication.identity.session_issued_at,
        )
    except Exception as error:
        response = _platform_billing_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_platform_manual_billing_grant(grant).model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post(
    "/api/platform/billing/manual-grants/{grant_id}/approve", response_model=PlatformManualBillingGrantResponse
)
async def approve_platform_manual_billing_grant(
    grant_id: UUID,
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> Response:
    return await _mutate_platform_manual_billing_grant(grant_id, request, container, idempotency_key, "approve")


@router.post("/api/platform/billing/manual-grants/{grant_id}/revoke", response_model=PlatformManualBillingGrantResponse)
async def revoke_platform_manual_billing_grant(
    grant_id: UUID,
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> Response:
    return await _mutate_platform_manual_billing_grant(grant_id, request, container, idempotency_key, "revoke")


@router.get("/api/billing/subscription", response_model=BillingStateResponse)
async def get_billing_subscription(request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if "billing:manage" not in capabilities_for(
            authentication.identity.user, authentication.identity.active_membership
        ):
            raise BillingOperationError(BillingErrorCode.CAPABILITY_REQUIRED)
        if container.settings.billing_provider_mode != "stripe_sandbox" or container.billing_sessions is None:
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        raw = await container.billing_sessions.read_stripe_state(context=_tenant_context(request, authentication))
        payload = BillingStateResponse.model_validate(
            {
                "contract": raw.get("contract"),
                "subscription": raw.get("subscription"),
                "checkout": raw.get("checkout"),
                "command": raw.get("command"),
                "manual_grant": raw.get("manual_grant"),
                "portal_available": container.settings.stripe_sandbox_portal_enabled,
            }
        )
    except Exception as error:
        response = _billing_api_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/billing/resume-checkout", response_model=BillingSessionResponse)
async def resume_checkout_session(request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if "billing:manage" not in capabilities_for(
            authentication.identity.user, authentication.identity.active_membership
        ):
            raise BillingOperationError(BillingErrorCode.CAPABILITY_REQUIRED)
        if container.settings.billing_provider_mode != "stripe_sandbox" or container.billing_sessions is None:
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        outcome = await container.billing_sessions.resume_stripe_checkout(
            context=_tenant_context(request, authentication),
            authorized=True,
            session_issued_at=authentication.identity.session_issued_at,
        )
    except Exception as error:
        response = _billing_api_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        BillingSessionResponse(url=outcome.url, expires_at=outcome.expires_at).model_dump(mode="json"),
        headers=NO_STORE_HEADERS,
    )


@router.get("/api/billing/checkout-options", response_model=BillingCheckoutOptionsResponse)
async def list_checkout_options(request: Request, container: ContainerDependency) -> Response:
    try:
        authentication = await required_authentication(request, container)
        if "billing:manage" not in capabilities_for(
            authentication.identity.user, authentication.identity.active_membership
        ):
            raise BillingOperationError(BillingErrorCode.CAPABILITY_REQUIRED)
        if container.settings.billing_provider_mode != "stripe_sandbox":
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        if container.get_organization_catalog is None:
            raise CatalogServiceUnavailable
        options = await container.get_organization_catalog.list_checkout_options(
            context=_tenant_context(request, authentication), has_capability=True
        )
        configured_currencies = {
            currency for currency, reference in container.settings.stripe_sandbox_price_references.items() if reference
        }
        payload = BillingCheckoutOptionsResponse(
            options=[
                BillingCheckoutOptionResponse(
                    id=option.id,
                    code=option.code.value,
                    version_number=option.version_number,
                    currency=option.currency.value,
                    amount_minor=option.amount_minor,
                    billing_cycle=option.billing_cycle,
                )
                for option in options
                if option.currency.value in configured_currencies
            ]
        )
    except Exception as error:
        response = _billing_api_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)


@router.post("/api/platform/billing/reconciliations", response_model=BillingReconciliationResponse, status_code=202)
async def request_billing_reconciliation(
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if idempotency_key is None:
            raise ValueError("Idempotency-Key est obligatoire.")
        payload = BillingReconciliationRequest.model_validate(await request.json())
        if container.billing_manual_reconciliation is None:
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        run_id = await container.billing_manual_reconciliation.request(
            context=ActorContext(authentication.identity.user.id, getattr(request.state, "request_id", "unknown")),
            organization_id=payload.organization_id,
            reason=ReconciliationReason(payload.reason_code),
            idempotency_key=idempotency_key,
            authorized="platform:billing:manage"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
            session_issued_at=authentication.identity.session_issued_at,
        )
    except Exception as error:
        response = _billing_api_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        BillingReconciliationResponse(run_id=run_id).model_dump(mode="json"), status_code=202, headers=NO_STORE_HEADERS
    )


@router.post("/api/billing/checkout-session", response_model=BillingSessionResponse)
async def create_checkout_session(
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if idempotency_key is None:
            raise ValueError("Idempotency-Key est obligatoire.")
        payload = BillingCheckoutSessionRequest.model_validate(await request.json())
        if container.billing_sessions is None:
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        outcome = await container.billing_sessions.create_checkout(
            context=_tenant_context(request, authentication),
            plan_version_id=payload.plan_version_id,
            idempotency_key=idempotency_key,
            return_target=BillingReturnTarget(payload.return_target),
            authorized="billing:manage"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
            session_issued_at=authentication.identity.session_issued_at,
        )
    except Exception as error:
        response = _billing_api_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        BillingSessionResponse(url=outcome.url, expires_at=outcome.expires_at).model_dump(mode="json"),
        headers=NO_STORE_HEADERS,
    )


@router.post("/api/billing/portal-session", response_model=BillingSessionResponse)
async def create_portal_session(
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if idempotency_key is None:
            raise ValueError("Idempotency-Key est obligatoire.")
        payload = BillingPortalSessionRequest.model_validate(await request.json())
        if container.billing_sessions is None:
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        if (
            container.settings.billing_provider_mode == "stripe_sandbox"
            and not container.settings.stripe_sandbox_portal_enabled
        ):
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        outcome = await container.billing_sessions.create_portal(
            context=_tenant_context(request, authentication),
            idempotency_key=idempotency_key,
            return_target=BillingReturnTarget(payload.return_target),
            authorized="billing:manage"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
            session_issued_at=authentication.identity.session_issued_at,
        )
    except Exception as error:
        response = _billing_api_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        BillingSessionResponse(url=outcome.url, expires_at=outcome.expires_at).model_dump(mode="json"),
        headers=NO_STORE_HEADERS,
    )


@router.post("/api/platform/billing/refunds", response_model=BillingRefundResponse)
async def request_billing_refund(
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if idempotency_key is None:
            raise ValueError("Idempotency-Key est obligatoire.")
        payload = BillingRefundRequest.model_validate(await request.json())
        if container.billing_refunds is None:
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        outcome = await container.billing_refunds.request_refund(
            context=ActorContext(authentication.identity.user.id, getattr(request.state, "request_id", "unknown")),
            organization_id=payload.organization_id,
            subscription_id=payload.subscription_id,
            idempotency_key=idempotency_key,
            approved=payload.approved,
            session_issued_at=authentication.identity.session_issued_at,
            authorized="platform:billing:manage"
            in capabilities_for(authentication.identity.user, authentication.identity.active_membership),
        )
    except Exception as error:
        response = _billing_api_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(
        BillingRefundResponse(refund_id=outcome.refund_id, state=outcome.state).model_dump(mode="json"),
        headers=NO_STORE_HEADERS,
    )


@router.post("/api/billing/webhooks/simulated", include_in_schema=False)
async def admit_simulated_billing_webhook(request: Request, container: ContainerDependency) -> Response:
    """Admission brute: aucune cookie/session/CSRF, aucune projection métier."""

    content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if content_type != "application/json":
        return _error(request, BillingErrorCode.WEBHOOK_INVALID)
    content_length = request.headers.get("content-length")
    if content_length and (not content_length.isdecimal() or int(content_length) > MAX_WEBHOOK_BODY_BYTES):
        return _error(request, BillingErrorCode.WEBHOOK_INVALID)
    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
        return _error(request, BillingErrorCode.WEBHOOK_INVALID)
    if container.billing_webhook_admission is None:
        return _error(request, BillingErrorCode.PROVIDER_DISABLED)
    try:
        result = await container.billing_webhook_admission.admit(
            raw_body=raw_body,
            signature_header=request.headers.get("x-billing-signature", ""),
        )
    except BillingOperationError as error:
        return _error(request, error.code)
    if result is BillingWebhookAdmissionCode.COLLISION:
        return _error(request, BillingErrorCode.EVENT_COLLISION)
    status_code = 202 if result is BillingWebhookAdmissionCode.ADMITTED else 200
    return JSONResponse({"status": "accepted"}, status_code=status_code, headers=NO_STORE_HEADERS)


@router.post("/api/billing/webhooks/stripe", include_in_schema=False)
async def admit_stripe_billing_webhook(request: Request, container: ContainerDependency) -> Response:
    """Admission Stripe sandbox: signature Stripe brute, sans cookie ni CSRF."""

    content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if content_type != "application/json":
        return _error(request, BillingErrorCode.WEBHOOK_INVALID)
    content_length = request.headers.get("content-length")
    if content_length and (not content_length.isdecimal() or int(content_length) > MAX_WEBHOOK_BODY_BYTES):
        return _error(request, BillingErrorCode.WEBHOOK_INVALID)
    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
        return _error(request, BillingErrorCode.WEBHOOK_INVALID)
    if container.billing_stripe_webhook_admission is None:
        return _error(request, BillingErrorCode.PROVIDER_DISABLED)
    try:
        result = await container.billing_stripe_webhook_admission.admit(
            raw_body=raw_body,
            signature_header=request.headers.get("stripe-signature", ""),
        )
    except BillingOperationError as error:
        return _error(request, error.code)
    if result is BillingWebhookAdmissionCode.COLLISION:
        return _error(request, BillingErrorCode.EVENT_COLLISION)
    status_code = 202 if result is BillingWebhookAdmissionCode.ADMITTED else 200
    return JSONResponse({"status": "accepted"}, status_code=status_code, headers=NO_STORE_HEADERS)


def _error(request: Request, code: BillingErrorCode) -> Response:
    messages = {
        BillingErrorCode.WEBHOOK_INVALID: "La livraison webhook est invalide.",
        BillingErrorCode.WEBHOOK_UNSUPPORTED: "La livraison webhook n'est pas prise en charge.",
        BillingErrorCode.EVENT_COLLISION: "La livraison webhook entre en conflit avec une preuve existante.",
        BillingErrorCode.PROVIDER_DISABLED: "Le fournisseur de facturation est indisponible.",
        BillingErrorCode.PROVIDER_UNAVAILABLE: "Le stockage de facturation est temporairement indisponible.",
    }
    return api_error(
        request, code.http_status, code.value, messages.get(code, "La livraison webhook est indisponible.")
    )


async def _authenticated_mutation(request: Request, container: ContainerDependency) -> RequestAuthentication:
    require_json_content_type(request)
    require_trusted_origin(request, container.settings.cors_allowed_origins)
    authentication = await required_authentication(request, container)
    require_csrf_token(request, authentication.identity.csrf_token)
    return authentication


def _tenant_context(request: Request, authentication: RequestAuthentication) -> TenantContext:
    membership = authentication.identity.active_membership
    if membership is None:
        raise BillingOperationError(BillingErrorCode.CAPABILITY_REQUIRED)
    return TenantContext(
        actor_id=authentication.identity.user.id,
        organization_id=membership.organization_id,
        request_id=getattr(request.state, "request_id", "unknown"),
    )


def _billing_api_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "request_rejected", "La requête a été refusée.")
    if isinstance(error, BillingOperationError):
        messages = {
            BillingErrorCode.CAPABILITY_REQUIRED: "Une autorisation Billing et une session récente sont requises.",
            BillingErrorCode.PROVIDER_DISABLED: "Le fournisseur de facturation est désactivé.",
            BillingErrorCode.PROVIDER_UNAVAILABLE: "Le fournisseur de facturation est temporairement indisponible.",
            BillingErrorCode.CATALOG_VERSION_UNAVAILABLE: "Cette version commerciale n'est pas disponible.",
            BillingErrorCode.CURRENCY_UNAVAILABLE: "Cette devise n'est pas commercialisée.",
            BillingErrorCode.SEAT_LIMIT_CONFLICT: "Cette offre ne couvre pas les sièges actuels.",
            BillingErrorCode.COMMAND_CONFLICT: "La clé d'idempotence désigne une autre commande.",
            BillingErrorCode.SUBSCRIPTION_EXISTS: "Un abonnement courant existe déjà.",
            BillingErrorCode.STATE_UNKNOWN: "L'état du paiement doit être vérifié.",
            BillingErrorCode.RECONCILIATION_REQUIRED: "Une réconciliation du paiement est requise.",
            BillingErrorCode.MANUAL_GRANT_NOT_FOUND: "L’attribution sandbox est introuvable.",
            BillingErrorCode.MANUAL_GRANT_CONFLICT: "Une attribution ou un forfait incompatible existe déjà.",
            BillingErrorCode.MANUAL_GRANT_APPROVAL_REQUIRED: "Un autre administrateur plateforme doit approuver cette attribution.",
            BillingErrorCode.MANUAL_GRANT_INVALID_STATE: "L’état de cette attribution ne permet pas cette action.",
        }
        return api_error(
            request,
            error.code.http_status,
            error.code.value,
            messages.get(error.code, "La commande Billing a été refusée."),
        )
    if isinstance(error, (AuthenticationServiceUnavailable, CatalogServiceUnavailable)):
        return api_error(request, 503, "billing_provider_unavailable", "Le service est temporairement indisponible.")
    if isinstance(error, (ValueError, TypeError)):
        return api_error(request, 422, "validation_failed", "La commande Billing est invalide.")
    return None


def _platform_billing_organization(item: object) -> PlatformBillingOrganizationResponse:
    return PlatformBillingOrganizationResponse.model_validate(item, from_attributes=True)


def _platform_manual_billing_grant(item: ManualBillingGrantView) -> PlatformManualBillingGrantResponse:
    return PlatformManualBillingGrantResponse(
        id=item.id,
        organization_id=item.organization_id,
        plan_version_id=item.plan_version_id,
        plan_code=item.plan_code,
        version_number=item.version_number,
        currency=item.currency,
        reason_code=item.reason_code.value,
        duration_days=item.duration_days,
        state=item.state.value,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        version=item.version,
    )


async def _mutate_platform_manual_billing_grant(
    grant_id: UUID,
    request: Request,
    container: ContainerDependency,
    idempotency_key: str | None,
    action: str,
) -> Response:
    try:
        authentication = await _authenticated_mutation(request, container)
        if idempotency_key is None:
            raise ValueError("Idempotency-Key est obligatoire.")
        payload = VersionedPlatformManualBillingGrantRequest.model_validate(await request.json())
        if container.manual_billing_grants is None:
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        context = ActorContext(authentication.identity.user.id, getattr(request.state, "request_id", "unknown"))
        has_platform_capability = "platform:billing:manage" in capabilities_for(
            authentication.identity.user, authentication.identity.active_membership
        )
        if action == "approve":
            grant = await container.manual_billing_grants.approve(
                context=context,
                grant_id=grant_id,
                expected_version=payload.version,
                idempotency_key=idempotency_key,
                has_platform_capability=has_platform_capability,
                session_issued_at=authentication.identity.session_issued_at,
            )
        elif action == "revoke":
            grant = await container.manual_billing_grants.revoke(
                context=context,
                grant_id=grant_id,
                expected_version=payload.version,
                idempotency_key=idempotency_key,
                has_platform_capability=has_platform_capability,
                session_issued_at=authentication.identity.session_issued_at,
            )
        else:
            raise ValueError("Action d’attribution inconnue.")
    except Exception as error:
        response = _platform_billing_error(request, error)
        if response is not None:
            return response
        raise
    return JSONResponse(_platform_manual_billing_grant(grant).model_dump(mode="json"), headers=NO_STORE_HEADERS)


def _platform_billing_error(request: Request, error: Exception) -> Response | None:
    if isinstance(error, AuthenticationRequired):
        return api_error(request, 401, "authentication_required", "Authentification requise.")
    if isinstance(error, CsrfValidationFailed):
        return api_error(request, 403, "request_rejected", "La requête a été refusée.")
    if isinstance(error, InsufficientCapability):
        return api_error(request, 403, "insufficient_capability", "Autorisation plateforme insuffisante.")
    if isinstance(error, ProvisioningResourceNotFound):
        return api_error(request, 404, "billing_organization_not_found", "Organisation de facturation introuvable.")
    if isinstance(error, BillingOperationError):
        return _billing_api_error(request, error)
    if isinstance(error, (AuthenticationServiceUnavailable, CatalogServiceUnavailable, ManualBillingGrantUnavailable)):
        return api_error(
            request, 503, "billing_consultation_unavailable", "La consultation Billing est temporairement indisponible."
        )
    if isinstance(error, (ValueError, TypeError)):
        return api_error(request, 422, "validation_failed", "Les filtres de consultation sont invalides.")
    return None
