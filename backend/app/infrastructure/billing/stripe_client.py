"""Transport Stripe limité au compte de test et à une version API fixe."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from ...application.errors import BillingOperationError
from ...domain.billing import BillingErrorCode
from ...domain.catalog import CurrencyCode
from .stripe_contract import STRIPE_API_VERSION

_STRIPE_ORIGIN = "https://api.stripe.com"


@dataclass(frozen=True, slots=True)
class StripeCheckoutDraft:
    reference: str
    url: str
    expires_at: datetime


class StripeSandboxClient:
    """Isole l'authentification, les erreurs et l'absence d'API réelle."""

    def __init__(self, *, test_secret_key: str, client: httpx.AsyncClient | None = None) -> None:
        if not test_secret_key.startswith("sk_test_"):
            raise ValueError("Une clé Stripe de test est obligatoire.")
        self._key = test_secret_key
        self._client = client

    async def get_price(self, reference: str, *, currency: CurrencyCode, amount_minor: int, billing_cycle: str) -> None:
        if not reference.startswith("price_") or not reference.isascii() or not reference.replace("_", "").isalnum():
            raise BillingOperationError(BillingErrorCode.CATALOG_VERSION_UNAVAILABLE)
        if amount_minor <= 0 or billing_cycle not in {"monthly", "annual"}:
            raise BillingOperationError(BillingErrorCode.CATALOG_VERSION_UNAVAILABLE)
        price = await self._request("GET", f"/v1/prices/{reference}")
        interval = "month" if billing_cycle == "monthly" else "year"
        if (
            price.get("object") != "price"
            or price.get("id") != reference
            or price.get("livemode") is not False
            or price.get("active") is not True
            or price.get("currency") != currency.value.lower()
            or price.get("unit_amount") != amount_minor
            or not isinstance(price.get("recurring"), dict)
            or price["recurring"].get("interval") != interval
            or price["recurring"].get("interval_count") != 1
            or price.get("type") != "recurring"
        ):
            raise BillingOperationError(BillingErrorCode.CATALOG_VERSION_UNAVAILABLE)

    async def create_checkout(
        self,
        *,
        customer_reference: str,
        price_reference: str,
        checkout_command_reference: str,
        currency: CurrencyCode,
        amount_minor: int,
        billing_cycle: str,
        return_origin: str,
        idempotency_key: str,
    ) -> StripeCheckoutDraft:
        self._require_reference(customer_reference, "cus_")
        self._require_uuid(checkout_command_reference)
        self._require_return_origin(return_origin)
        await self.get_price(price_reference, currency=currency, amount_minor=amount_minor, billing_cycle=billing_cycle)
        result = await self._request(
            "POST",
            "/v1/checkout/sessions",
            data={
                "mode": "subscription",
                "customer": customer_reference,
                "line_items[0][price]": price_reference,
                "line_items[0][quantity]": "1",
                "client_reference_id": checkout_command_reference,
                "subscription_data[metadata][billing_command_id]": checkout_command_reference,
                "success_url": f"{return_origin}/app/billing?checkout=success",
                "cancel_url": f"{return_origin}/app/billing?checkout=cancel",
                "allow_promotion_codes": "false",
                "payment_method_types[0]": "card",
            },
            idempotency_key=idempotency_key,
        )
        reference = self._require_reference(result.get("id"), "cs_test_")
        url = result.get("url")
        if (
            result.get("livemode") is not False
            or not isinstance(url, str)
            or not url.startswith("https://checkout.stripe.com/")
        ):
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        return StripeCheckoutDraft(reference, url, self._timestamp(result.get("expires_at")))

    async def create_customer(self, *, organization_reference: str, idempotency_key: str) -> str:
        """Crée un client technique sans PII, lié uniquement à l'organisation interne."""

        self._require_uuid(organization_reference)
        result = await self._request(
            "POST",
            "/v1/customers",
            data={"metadata[organization_id]": organization_reference},
            idempotency_key=idempotency_key,
        )
        if result.get("object") != "customer" or result.get("livemode") is not False:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        return self._require_reference(result.get("id"), "cus_")

    async def resume_checkout(
        self,
        *,
        reference: str,
        command_reference: str,
        customer_reference: str,
        price_reference: str,
        currency: CurrencyCode,
    ) -> StripeCheckoutDraft:
        self._require_uuid(command_reference)
        self._require_reference(customer_reference, "cus_")
        self._require_reference(price_reference, "price_")
        result = await self.read_object("checkout", reference)
        expires_at = self._timestamp(result.get("expires_at"))
        url = result.get("url")
        if (
            result.get("mode") != "subscription"
            or result.get("status") != "open"
            or result.get("client_reference_id") != command_reference
            or result.get("customer") != customer_reference
            or result.get("currency") != currency.value.lower()
            or result.get("subscription") is not None
            or expires_at <= datetime.now(UTC)
            or not isinstance(url, str)
            or not url.startswith("https://checkout.stripe.com/")
        ):
            raise BillingOperationError(BillingErrorCode.RECONCILIATION_REQUIRED)
        lines = await self._request("GET", f"/v1/checkout/sessions/{reference}/line_items", params={"limit": "2"})
        items = lines.get("data")
        if (
            lines.get("has_more") is not False
            or not isinstance(items, list)
            or len(items) != 1
            or not isinstance(items[0], dict)
            or items[0].get("quantity") != 1
            or not isinstance(items[0].get("price"), dict)
            or items[0]["price"].get("id") != price_reference
            or items[0]["price"].get("currency") != currency.value.lower()
        ):
            raise BillingOperationError(BillingErrorCode.RECONCILIATION_REQUIRED)
        return StripeCheckoutDraft(reference, url, expires_at)

    async def get_subscription(self, reference: str) -> dict[str, Any]:
        self._require_reference(reference, "sub_")
        result = await self._request("GET", f"/v1/subscriptions/{reference}")
        if (
            result.get("id") != reference
            or result.get("object") != "subscription"
            or result.get("livemode") is not False
        ):
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        return result

    async def read_object(self, kind: str, reference: str) -> dict[str, Any]:
        path, prefix, object_type = {
            "subscription": ("subscriptions", "sub_", "subscription"),
            "invoice": ("invoices", "in_", "invoice"),
            "checkout": ("checkout/sessions", "cs_test_", "checkout.session"),
            "refund": ("refunds", "re_", "refund"),
            "charge": ("charges", "ch_", "charge"),
        }[kind]
        self._require_reference(reference, prefix)
        result = await self._request("GET", f"/v1/{path}/{reference}")
        if result.get("id") != reference or result.get("object") != object_type:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        # Refund has no livemode field; its charge is checked independently.
        if kind != "refund" and result.get("livemode") is not False:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        return result

    async def invoice_for_payment(self, reference: str) -> dict[str, Any]:
        self._require_reference(reference, "pi_")
        result = await self._request(
            "GET",
            "/v1/invoice_payments",
            params={
                "payment[type]": "payment_intent",
                "payment[payment_intent]": reference,
                "status": "paid",
                "limit": "100",
            },
        )
        payments = result.get("data")
        if result.get("has_more") is not False or not isinstance(payments, list) or len(payments) != 1:
            raise BillingOperationError(BillingErrorCode.RECONCILIATION_REQUIRED)
        payment = payments[0]
        if payment.get("payment", {}).get("payment_intent") != reference or payment.get("status") != "paid":
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        return await self.read_object("invoice", payment["invoice"])

    async def read_events(self, *, cursor: str | None, starts_at: datetime, ends_at: datetime) -> dict[str, Any]:
        from .stripe_contract import STRIPE_PLANNED_WEBHOOK_EVENTS

        params = {
            "limit": "50",
            "created[gte]": str(int(starts_at.timestamp())),
            "created[lt]": str(int(ends_at.timestamp())),
        }
        params.update({f"types[{i}]": value for i, value in enumerate(STRIPE_PLANNED_WEBHOOK_EVENTS)})
        if cursor is not None:
            self._require_reference(cursor, "evt_")
            params["starting_after"] = cursor
        return await self._request("GET", "/v1/events", params=params)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, str] | None = None,
        idempotency_key: str = "",
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._key}", "Stripe-Version": STRIPE_API_VERSION}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            if self._client is None:
                async with httpx.AsyncClient(base_url=_STRIPE_ORIGIN, timeout=10.0) as client:
                    response = await client.request(method, path, data=data, headers=headers, params=params)
            else:
                response = await self._client.request(
                    method, f"{_STRIPE_ORIGIN}{path}", data=data, headers=headers, params=params
                )
            if response.status_code >= 400:
                code = (
                    BillingErrorCode.CATALOG_VERSION_UNAVAILABLE
                    if response.status_code == 404 and path.startswith("/v1/prices/")
                    else BillingErrorCode.PROVIDER_UNAVAILABLE
                )
                raise BillingOperationError(code)
            payload = response.json()
            if not isinstance(payload, dict):
                raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
            return payload
        except (httpx.TimeoutException, httpx.TransportError) as error:
            code = (
                BillingErrorCode.RECONCILIATION_REQUIRED if method == "POST" else BillingErrorCode.PROVIDER_UNAVAILABLE
            )
            raise BillingOperationError(code) from error
        except (ValueError, httpx.DecodingError) as error:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN) from error

    @staticmethod
    def _require_reference(value: object, prefix: str) -> str:
        if not isinstance(value, str) or not value.startswith(prefix) or not value.isascii() or len(value) > 255:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        if not value.replace("_", "").isalnum():
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        return value

    @staticmethod
    def _require_uuid(value: str) -> None:
        try:
            UUID(value)
        except (TypeError, ValueError, AttributeError) as error:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN) from error

    @staticmethod
    def _require_return_origin(origin: str) -> None:
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"}:
            raise ValueError("Origine de retour invalide.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Origine de retour invalide.")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("Une origine HTTP distante est interdite.")

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        return datetime.fromtimestamp(value, UTC)
