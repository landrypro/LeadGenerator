"""Point d'entrée public mais non authentifié des livraisons P53-04."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from ....application.errors import BillingOperationError
from ....application.ports.billing import BillingWebhookAdmissionCode
from ....domain.billing import BillingErrorCode
from ....infrastructure.billing.webhooks import MAX_WEBHOOK_BODY_BYTES
from ..dependencies import ContainerDependency
from ..responses import NO_STORE_HEADERS, api_error

router = APIRouter()


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
