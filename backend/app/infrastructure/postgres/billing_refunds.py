"""Commandes plateforme durables de remboursement simulé P53-07."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...application.errors import BillingOperationError
from ...application.ports.billing import (
    BillingCommandState,
    BillingRefundCommand,
    BillingRefundPreparation,
    BillingRefundRepository,
)
from ...application.tenancy import ActorContext
from ...domain.billing import BillingErrorCode


class SqlAlchemyBillingRefundRepository(BillingRefundRepository):
    def __init__(self, actor_unit_of_work_factory: Callable[[ActorContext], Any]) -> None:
        self._actor_unit_of_work_factory = actor_unit_of_work_factory

    async def prepare_refund(
        self,
        *,
        context: ActorContext,
        organization_id: UUID,
        subscription_id: UUID,
        command_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        now: Any,
    ) -> BillingRefundPreparation:
        result = await self._json_call(
            context,
            "SELECT app_private.prepare_platform_billing_refund(:command_id,:organization_id,:subscription_id,:key,:fingerprint,:now)",
            {
                "command_id": command_id,
                "organization_id": organization_id,
                "subscription_id": subscription_id,
                "key": idempotency_key_digest,
                "fingerprint": request_fingerprint,
                "now": now,
            },
        )
        _raise(result)
        try:
            return BillingRefundPreparation(
                command_id=UUID(str(result["command_id"])),
                refund_id=UUID(str(result["refund_id"])),
                state=BillingCommandState(str(result["status"])),
                command=BillingRefundCommand(organization_id, str(result["payment_reference"])),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN) from error

    async def complete_refund(
        self, *, context: ActorContext, preparation: BillingRefundPreparation, provider_event_id: str
    ) -> None:
        result = await self._json_call(
            context,
            "SELECT app_private.complete_platform_billing_refund(:command_id,:provider_event_id)",
            {"command_id": preparation.command_id, "provider_event_id": provider_event_id},
        )
        _raise(result)

    async def mark_refund(self, *, context: ActorContext, command_id: UUID, unknown: bool) -> None:
        try:
            async with self._actor_unit_of_work_factory(context) as unit:
                result = await unit.session.scalar(
                    text("SELECT app_private.mark_platform_billing_refund(:command_id,:status)"),
                    {"command_id": command_id, "status": "unknown" if unknown else "failed"},
                )
                if result not in {"unknown", "failed", "unchanged"}:
                    raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
                await unit.commit()
        except BillingOperationError:
            raise
        except SQLAlchemyError as error:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE) from error

    async def _json_call(
        self, context: ActorContext, statement: str, parameters: dict[str, object]
    ) -> dict[str, object]:
        try:
            async with self._actor_unit_of_work_factory(context) as unit:
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


def _raise(result: dict[str, object]) -> None:
    if result.get("code") in {"reserved", "replayed", "succeeded"}:
        return
    try:
        raise BillingOperationError(BillingErrorCode(str(result.get("code"))))
    except ValueError as error:
        raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN) from error
