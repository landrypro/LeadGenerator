"""Adaptateur PostgreSQL du parcours d'attribution Billing sandbox."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.errors import ManualBillingGrantUnavailable
from ...application.ports.manual_billing_grants import (
    ManualBillingGrantMutationCode,
    ManualBillingGrantMutationResult,
    ManualBillingGrantOption,
    ManualBillingGrantView,
)
from ...domain.billing import ManualBillingGrantReasonCode, ManualBillingGrantState


class SqlAlchemyManualBillingGrantMutations:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_options(self, *, now: datetime) -> tuple[ManualBillingGrantOption, ...]:
        value = await self._scalar("SELECT app_private.list_platform_manual_billing_grant_options(:now)", {"now": now})
        raw_items = value.get("items") if isinstance(value, dict) else None
        if not isinstance(raw_items, list) or not all(isinstance(item, dict) for item in raw_items):
            raise ManualBillingGrantUnavailable
        try:
            return tuple(
                ManualBillingGrantOption(
                    plan_version_id=UUID(str(item["plan_version_id"])),
                    code=str(item["code"]),
                    version_number=int(item["version_number"]),
                    currency=str(item["currency"]),
                    amount_minor=int(item["amount_minor"]),
                )
                for item in raw_items
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ManualBillingGrantUnavailable from error

    async def propose(
        self,
        *,
        grant_id: UUID,
        operation_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        organization_id: UUID,
        plan_version_id: UUID,
        reason_code: ManualBillingGrantReasonCode,
        duration_days: int,
        now: datetime,
    ) -> ManualBillingGrantMutationResult:
        return self._result(
            await self._json(
                """
                SELECT app_private.propose_platform_manual_billing_grant(
                  :grant_id,:operation_id,:idempotency_key_digest,:request_fingerprint,
                  :organization_id,:plan_version_id,:reason_code,:duration_days,:now
                )
                """,
                {
                    "grant_id": grant_id,
                    "operation_id": operation_id,
                    "idempotency_key_digest": idempotency_key_digest,
                    "request_fingerprint": request_fingerprint,
                    "organization_id": organization_id,
                    "plan_version_id": plan_version_id,
                    "reason_code": reason_code.value,
                    "duration_days": duration_days,
                    "now": now,
                },
            )
        )

    async def approve(
        self,
        *,
        grant_id: UUID,
        operation_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        expected_version: int,
        now: datetime,
    ) -> ManualBillingGrantMutationResult:
        return self._result(
            await self._json(
                """
                SELECT app_private.approve_platform_manual_billing_grant(
                  :grant_id,:operation_id,:idempotency_key_digest,:request_fingerprint,:expected_version,:now
                )
                """,
                {
                    "grant_id": grant_id,
                    "operation_id": operation_id,
                    "idempotency_key_digest": idempotency_key_digest,
                    "request_fingerprint": request_fingerprint,
                    "expected_version": expected_version,
                    "now": now,
                },
            )
        )

    async def revoke(
        self,
        *,
        grant_id: UUID,
        operation_id: UUID,
        idempotency_key_digest: str,
        request_fingerprint: str,
        expected_version: int,
        now: datetime,
    ) -> ManualBillingGrantMutationResult:
        return self._result(
            await self._json(
                """
                SELECT app_private.revoke_platform_manual_billing_grant(
                  :grant_id,:operation_id,:idempotency_key_digest,:request_fingerprint,:expected_version,:now
                )
                """,
                {
                    "grant_id": grant_id,
                    "operation_id": operation_id,
                    "idempotency_key_digest": idempotency_key_digest,
                    "request_fingerprint": request_fingerprint,
                    "expected_version": expected_version,
                    "now": now,
                },
            )
        )

    async def _scalar(self, statement: str, parameters: dict[str, object]) -> object:
        try:
            return await self._session.scalar(text(statement), parameters)
        except SQLAlchemyError as error:
            raise ManualBillingGrantUnavailable from error

    async def _json(self, statement: str, parameters: dict[str, object]) -> dict[str, Any]:
        value = await self._scalar(statement, parameters)
        if not isinstance(value, dict) or not isinstance(value.get("code"), str):
            raise ManualBillingGrantUnavailable
        return value

    @staticmethod
    def _result(value: dict[str, Any]) -> ManualBillingGrantMutationResult:
        try:
            code = ManualBillingGrantMutationCode(value["code"])
        except ValueError as error:
            raise ManualBillingGrantUnavailable from error
        grant = None
        raw_grant = value.get("grant")
        if isinstance(raw_grant, dict):
            try:
                grant = ManualBillingGrantView(
                    id=UUID(str(raw_grant["id"])),
                    organization_id=UUID(str(raw_grant["organization_id"])),
                    plan_version_id=UUID(str(raw_grant["plan_version_id"])),
                    plan_code=str(raw_grant["plan_code"]),
                    version_number=int(raw_grant["version_number"]),
                    currency=str(raw_grant["currency"]),
                    reason_code=ManualBillingGrantReasonCode(str(raw_grant["reason_code"])),
                    duration_days=int(raw_grant["duration_days"]),
                    state=ManualBillingGrantState(str(raw_grant["state"])),
                    starts_at=_datetime_or_none(raw_grant.get("starts_at")),
                    ends_at=_datetime_or_none(raw_grant.get("ends_at")),
                    version=int(raw_grant["version"]),
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ManualBillingGrantUnavailable from error
        current_version = value.get("current_version")
        return ManualBillingGrantMutationResult(
            code=code,
            grant=grant,
            current_version=int(current_version) if current_version is not None else None,
        )


def _datetime_or_none(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ManualBillingGrantUnavailable from error
    raise ManualBillingGrantUnavailable
