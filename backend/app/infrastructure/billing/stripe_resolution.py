"""Authenticated, minimal evidence for the Stripe projection worker."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ...application.errors import BillingOperationError
from ...domain.billing import BillingErrorCode
from .stripe_client import StripeSandboxClient
from .stripe_contract import _checkout_command_id, _reference, _timestamp, subscription_snapshot_from_object


def invoice_evidence(invoice: dict[str, Any], subscription: dict[str, Any]) -> dict[str, Any]:
    """V1 is one recurring item, no proration, quantity one, no conversion."""
    parent = invoice["parent"]
    lines = invoice["lines"]
    if (
        parent["type"] != "subscription_details"
        or parent["subscription_details"]["subscription"] != subscription["id"]
        or invoice["customer"] != subscription["customer"]
        or invoice["currency"] != subscription["currency"]
        or lines["has_more"] is not False
        or len(lines["data"]) != 1
    ):
        raise ValueError("invoice_mapping_invalid")
    line = lines["data"][0]
    details = line["parent"]["subscription_item_details"]
    if (
        line["parent"]["type"] != "subscription_item_details"
        or details["subscription"] != subscription["id"]
        or details["proration"] is not False
        or line["quantity"] != 1
        or line["currency"] != invoice["currency"]
        or line["pricing"]["price_details"]["price"] != subscription["items"]["data"][0]["price"]["id"]
    ):
        raise ValueError("invoice_line_invalid")
    for amount in (line["amount"], invoice["amount_due"], invoice["amount_paid"], invoice["amount_remaining"]):
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("invoice_amount_invalid")
    start, end = _timestamp(line["period"]["start"]), _timestamp(line["period"]["end"])
    if end <= start:
        raise ValueError("invoice_period_invalid")
    return {
        "reference": _reference(invoice["id"], "in_"),
        "status": invoice["status"],
        "amount_minor": line["amount"],
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "paid": invoice["status"] == "paid"
        and invoice["amount_due"] > 0
        and invoice["amount_paid"] >= invoice["amount_due"]
        and invoice["amount_remaining"] == 0
        and invoice.get("paid_out_of_band", False) is False,
    }


class StripeEventResolver:
    def __init__(self, client: StripeSandboxClient) -> None:
        self.client = client

    async def resolve(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Start time fences concurrent reads; it is an observation time, not a Stripe event version.
        observed_at = datetime.now(UTC)
        try:
            reference = payload["provider_object_reference"]
            kind = payload.get("provider_event_kind", "customer.subscription.updated")
            related_invoice = None
            refund = None
            checkout = None
            if kind.startswith("customer.subscription."):
                subscription_reference = _reference(reference, "sub_")
            elif kind.startswith("invoice."):
                related_invoice = await self.client.read_object("invoice", reference)
                subscription_reference = related_invoice["parent"]["subscription_details"]["subscription"]
            elif kind == "checkout.session.completed":
                checkout = await self.client.read_object("checkout", reference)
                if checkout["mode"] != "subscription" or checkout["status"] != "complete":
                    raise ValueError("checkout_not_completed")
                subscription_reference = checkout["subscription"]
            elif kind == "refund.updated":
                refund = await self.client.read_object("refund", reference)
                charge = await self.client.read_object("charge", refund["charge"])
                if charge["payment_intent"] != refund["payment_intent"] or charge["currency"] != refund["currency"]:
                    raise ValueError("refund_charge_mismatch")
                related_invoice = await self.client.invoice_for_payment(refund["payment_intent"])
                subscription_reference = related_invoice["parent"]["subscription_details"]["subscription"]
            else:
                raise ValueError("unsupported_event")
            subscription = await self.client.read_object("subscription", subscription_reference)
            snapshot = subscription_snapshot_from_object(subscription, observed_at)
            command = _checkout_command_id(subscription)
            if checkout is not None and (
                checkout["customer"] != subscription["customer"]
                or checkout["currency"] != subscription["currency"]
                or checkout["client_reference_id"] != str(command)
            ):
                raise ValueError("checkout_mapping_invalid")
            related = invoice_evidence(related_invoice, subscription) if related_invoice else None
            latest_reference = subscription.get("latest_invoice")
            latest = None
            if latest_reference:
                invoice = (
                    related_invoice
                    if related_invoice and related_invoice["id"] == latest_reference
                    else await self.client.read_object("invoice", latest_reference)
                )
                latest = invoice_evidence(invoice, subscription)
            refund_evidence = None
            if refund is not None:
                if (
                    refund["currency"] != subscription["currency"]
                    or charge["customer"] != subscription["customer"]
                    or refund["status"] not in {"pending", "requires_action", "succeeded", "failed", "canceled"}
                    or isinstance(refund["amount"], bool)
                    or not isinstance(refund["amount"], int)
                    or refund["amount"] <= 0
                    or refund["amount"] > charge["amount"]
                ):
                    raise ValueError("refund_invalid")
                refund_evidence = {
                    "reference": refund["id"],
                    "status": refund["status"],
                    "amount_minor": refund["amount"],
                    "invoice_reference": related["reference"] if related is not None else "",
                }
            return {
                "observed_at": observed_at.isoformat(),
                "checkout_command_id": str(command) if command else None,
                "checkout_reference": checkout["id"] if checkout else None,
                "subscription": {
                    "reference": snapshot.provider_subscription_reference,
                    "customer_reference": snapshot.provider_customer_reference,
                    "price_reference": snapshot.provider_price_reference,
                    "currency": snapshot.currency.value,
                    "state": snapshot.state.value,
                    "provider_status": subscription["status"],
                    "current_period_start": snapshot.period.starts_at.isoformat(),
                    "current_period_end": snapshot.period.ends_at.isoformat(),
                    "cancel_at_period_end": snapshot.cancel_at_period_end,
                },
                "invoice": latest,
                "related_invoice": related,
                "refund": refund_evidence,
            }
        except BillingOperationError:
            raise
        except (KeyError, TypeError, ValueError, IndexError, OverflowError) as error:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN) from error
