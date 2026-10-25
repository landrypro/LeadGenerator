"""API Billing interne P53-06 et admission publique des webhooks simulés."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, Response

from ....application.errors import (
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    BillingOperationError,
    CsrfValidationFailed,
)
from ....application.ports.billing import BillingReturnTarget, BillingWebhookAdmissionCode
from ....application.tenancy import ActorContext, TenantContext
from ....application.use_cases.billing_reconciliation import ReconciliationReason
from ....domain.billing import BillingErrorCode
from ....domain.identity import capabilities_for
from ....infrastructure.billing.webhooks import MAX_WEBHOOK_BODY_BYTES
from ..dependencies import ContainerDependency, RequestAuthentication, required_authentication
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import (
    BillingCheckoutSessionRequest,
    BillingPortalSessionRequest,
    BillingReconciliationRequest,
    BillingReconciliationResponse,
    BillingRefundRequest,
    BillingRefundResponse,
    BillingSessionResponse,
)
from ..security import require_csrf_token, require_json_content_type, require_trusted_origin

router = APIRouter()


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
        }
        return api_error(
            request,
            error.code.http_status,
            error.code.value,
            messages.get(error.code, "La commande Billing a été refusée."),
        )
    if isinstance(error, AuthenticationServiceUnavailable):
        return api_error(request, 503, "billing_provider_unavailable", "Le service est temporairement indisponible.")
    if isinstance(error, (ValueError, TypeError)):
        return api_error(request, 422, "validation_failed", "La commande Billing est invalide.")
    return None
