"""Persistance transactionnelle des commandes Billing P53-06."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...application.errors import BillingOperationError
from ...application.ports.billing import (
    BillingCheckoutCommand,
    BillingCheckoutPreparation,
    BillingCommandState,
    BillingPortalCommand,
    BillingPortalPreparation,
    BillingReturnTarget,
    CheckoutSession,
    PortalSession,
)
from ...application.tenancy import TenantContext
from ...domain.billing import BillingErrorCode
from ...domain.catalog import CurrencyCode


class SqlAlchemyBillingCommandRepository:
    def __init__(
        self,
        tenant_unit_of_work_factory: Callable[[TenantContext], Any],
        *,
        stripe_price_references: dict[str, str] | None = None,
    ) -> None:
        self._tenant_unit_of_work_factory = tenant_unit_of_work_factory
        self._stripe_price_references = stripe_price_references

    async def prepare_checkout(
        self,
        *,
        context: TenantContext,
        command_id: UUID,
        plan_version_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        now: Any,
    ) -> BillingCheckoutPreparation:
        result = await self._json_call(
            context,
            (
                "SELECT app_private.prepare_stripe_sandbox_checkout(:command_id,:plan_version_id,:key,:fingerprint,:now)"
                if self._stripe_price_references is not None
                else "SELECT app_private.prepare_billing_checkout(:command_id,:plan_version_id,:key,:fingerprint,:now)"
            ),
            {
                "command_id": command_id,
                "plan_version_id": plan_version_id,
                "key": idempotency_key_digest,
                "fingerprint": request_fingerprint,
                "now": now,
            },
        )
        _raise_public_error(result)
        try:
            returned_id = UUID(str(result["command_id"]))
            state = BillingCommandState(str(result["status"]))
            currency = CurrencyCode(str(result["currency"]))
            price_reference = str(result["provider_price_reference"])
            if self._stripe_price_references is not None:
                price_reference = self._stripe_price_references.get(currency.value, "")
                if not price_reference:
                    raise BillingOperationError(BillingErrorCode.CURRENCY_UNAVAILABLE)
            amount_minor = result.get("amount_minor", 0)
            if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
                raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
            customer_reference = (
                await self._stripe_customer_reference(context) if self._stripe_price_references is not None else None
            )
            command = BillingCheckoutCommand(
                organization_id=context.organization_id,
                plan_version_id=UUID(str(result["plan_version_id"])),
                currency=currency,
                provider_price_reference=price_reference,
                return_target=BillingReturnTarget.SUBSCRIPTION,
                amount_minor=amount_minor,
                billing_cycle=str(result.get("billing_cycle", "monthly")),
                provider_customer_reference=customer_reference,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN) from error
        return BillingCheckoutPreparation(returned_id, state, command)

    async def _stripe_customer_reference(self, context: TenantContext) -> str | None:
        try:
            async with self._tenant_unit_of_work_factory(context) as unit:
                reference = await unit.session.scalar(text("SELECT app_private.tenant_stripe_customer_reference()"))
        except SQLAlchemyError as error:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE) from error
        if reference is None:
            return None
        if (
            not isinstance(reference, str)
            or not reference.startswith("cus_")
            or not reference.isascii()
            or not reference.replace("_", "").isalnum()
        ):
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        return reference

    async def prepare_portal(
        self,
        *,
        context: TenantContext,
        command_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        now: Any,
    ) -> BillingPortalPreparation:
        result = await self._json_call(
            context,
            "SELECT app_private.prepare_billing_portal(:command_id,:key,:fingerprint,:now)",
            {"command_id": command_id, "key": idempotency_key_digest, "fingerprint": request_fingerprint, "now": now},
        )
        _raise_public_error(result)
        try:
            returned_id = UUID(str(result["command_id"]))
            state = BillingCommandState(str(result["status"]))
            command = BillingPortalCommand(
                organization_id=context.organization_id,
                provider_customer_reference=str(result["provider_customer_reference"]),
                return_target=BillingReturnTarget.SUBSCRIPTION,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN) from error
        return BillingPortalPreparation(returned_id, state, command)

    async def complete_checkout(
        self,
        *,
        context: TenantContext,
        preparation: BillingCheckoutPreparation,
        session: CheckoutSession,
    ) -> None:
        snapshot = session.subscription
        if snapshot is None:
            await self._complete_stripe_checkout(context=context, preparation=preparation, session=session)
            return
        parameters = {
            "command_id": preparation.command_id,
            "plan_version_id": preparation.command.plan_version_id,
            "checkout_reference": session.provider_checkout_reference,
            "customer_reference": session.provider_customer_reference,
            "subscription_reference": session.provider_subscription_reference,
            "currency": snapshot.currency.value,
            "price_reference": snapshot.provider_price_reference,
            "period_start": snapshot.period.starts_at,
            "period_end": snapshot.period.ends_at,
            "provider_updated_at": snapshot.provider_updated_at,
        }
        try:
            async with self._tenant_unit_of_work_factory(context) as unit:
                raw = await unit.session.scalar(
                    text(
                        """
                        SELECT app_private.complete_billing_checkout(
                          :command_id,:plan_version_id,'simulated',:checkout_reference,
                          :customer_reference,:subscription_reference,:currency,:price_reference,
                          :period_start,:period_end,:provider_updated_at
                        )
                        """
                    ),
                    parameters,
                )
                result = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(result, dict):
                    raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
                _require_completion(cast(dict[str, object], result))
                persisted = await unit.session.scalar(
                    text(
                        """
                        SELECT app_private.record_simulated_billing_checkout_snapshot(
                          :subscription_reference,:customer_reference,:price_reference,:currency,
                          :period_start,:period_end,:provider_updated_at
                        )
                        """
                    ),
                    parameters,
                )
                if persisted is not True:
                    raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
                await unit.commit()
        except BillingOperationError:
            raise
        except SQLAlchemyError as error:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE) from error

    async def _complete_stripe_checkout(
        self, *, context: TenantContext, preparation: BillingCheckoutPreparation, session: CheckoutSession
    ) -> None:
        if self._stripe_price_references is None:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        try:
            async with self._tenant_unit_of_work_factory(context) as unit:
                raw = await unit.session.scalar(
                    text(
                        "SELECT app_private.complete_stripe_sandbox_checkout("
                        ":command_id,:plan_version_id,:checkout_reference,:customer_reference,"
                        ":price_reference,:currency,:expires_at)"
                    ),
                    {
                        "command_id": preparation.command_id,
                        "plan_version_id": preparation.command.plan_version_id,
                        "checkout_reference": session.provider_checkout_reference,
                        "customer_reference": session.provider_customer_reference,
                        "price_reference": preparation.command.provider_price_reference,
                        "currency": preparation.command.currency.value,
                        "expires_at": session.expires_at,
                    },
                )
                result = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(result, dict):
                    raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
                _require_completion(cast(dict[str, object], result))
                await unit.commit()
        except BillingOperationError:
            raise
        except SQLAlchemyError as error:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE) from error

    async def complete_portal(
        self,
        *,
        context: TenantContext,
        preparation: BillingPortalPreparation,
        session: PortalSession,
    ) -> None:
        result = await self._json_call(
            context,
            "SELECT app_private.complete_billing_portal(:command_id,:reference)",
            {"command_id": preparation.command_id, "reference": session.provider_portal_reference},
        )
        _require_completion(result)

    async def mark_failed(self, *, context: TenantContext, command_id: UUID, reason: BillingErrorCode) -> None:
        await self._mark(context, command_id, BillingCommandState.FAILED, reason)

    async def mark_unknown(self, *, context: TenantContext, command_id: UUID) -> None:
        await self._mark(context, command_id, BillingCommandState.UNKNOWN, BillingErrorCode.RECONCILIATION_REQUIRED)

    async def _mark(
        self,
        context: TenantContext,
        command_id: UUID,
        state: BillingCommandState,
        reason: BillingErrorCode,
    ) -> None:
        try:
            async with self._tenant_unit_of_work_factory(context) as unit:
                result = await unit.session.scalar(
                    text("SELECT app_private.mark_billing_command(:command_id,:status,:reason)"),
                    {"command_id": command_id, "status": state.value, "reason": reason.value},
                )
                if result not in {state.value, "unchanged"}:
                    raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
                await unit.commit()
        except BillingOperationError:
            raise
        except SQLAlchemyError as error:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE) from error

    async def _json_call(
        self, context: TenantContext, statement: str, parameters: dict[str, object]
    ) -> dict[str, object]:
        try:
            async with self._tenant_unit_of_work_factory(context) as unit:
                raw = await unit.session.scalar(text(statement), parameters)
                result = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(result, dict):
                    raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
                await unit.commit()
                return cast(dict[str, object], result)
        except BillingOperationError:
            raise
        except SQLAlchemyError as error:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE) from error


def _raise_public_error(result: dict[str, object]) -> None:
    code = result.get("code")
    if code in {"reserved", "replayed"}:
        return
    try:
        raise BillingOperationError(BillingErrorCode(str(code)))
    except ValueError as error:
        raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN) from error


def _require_completion(result: dict[str, object]) -> None:
    if result.get("code") not in {"succeeded", "replayed"}:
        _raise_public_error(result)
