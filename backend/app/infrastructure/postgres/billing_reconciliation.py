"""Lecture des preuves simulées et orchestration de la réconciliation."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.errors import BillingOperationError
from ...application.ports.billing import BillingReconciliationDifferenceCode, NormalizedSubscriptionSnapshot
from ...application.tenancy import ActorContext
from ...application.use_cases.billing_reconciliation import (
    ReconciliationCandidate,
    ReconciliationLease,
    ReconciliationRead,
    ReconciliationReadStatus,
    ReconciliationReason,
    ReconciliationScheduleKind,
    ReconciliationWindow,
)
from ...domain.billing import BillingErrorCode, BillingPeriod, SubscriptionState
from ...domain.catalog import CurrencyCode
from .billing_commands import _raise_public_error


class PostgresSimulatedBillingSubscriptionReader:
    """Relit la preuve fournisseur simulée partagée entre l'API et le worker."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_subscription(self, *, provider_subscription_reference: str) -> NormalizedSubscriptionSnapshot:
        if not provider_subscription_reference.strip():
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        try:
            async with self._sessions.begin() as session:
                raw = await session.scalar(
                    text("SELECT app_private.read_simulated_billing_provider_subscription(:reference)"),
                    {"reference": provider_subscription_reference},
                )
        except SQLAlchemyError as error:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE) from error
        value = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(value, dict) or value.get("status") != "found":
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        try:
            cancel_at_period_end = value["cancel_at_period_end"]
            if not isinstance(cancel_at_period_end, bool):
                raise ValueError("invalid cancel_at_period_end")
            return NormalizedSubscriptionSnapshot(
                provider_subscription_reference=str(value["subscription_reference"]),
                provider_customer_reference=str(value["customer_reference"]),
                provider_price_reference=str(value["price_reference"]),
                state=SubscriptionState(value["state"]),
                currency=CurrencyCode(value["currency"]),
                period=BillingPeriod(
                    datetime.fromisoformat(value["period_start"]), datetime.fromisoformat(value["period_end"])
                ),
                cancel_at_period_end=cancel_at_period_end,
                provider_updated_at=datetime.fromisoformat(value["provider_updated_at"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN) from error


class PostgresBillingManualReconciliationRepository:
    def __init__(self, actor_unit_of_work_factory: Callable[[ActorContext], Any]) -> None:
        self._actor_unit_of_work_factory = actor_unit_of_work_factory

    async def request(
        self, *, context: ActorContext, organization_id: UUID, reason: ReconciliationReason, key_digest: str
    ) -> UUID:
        try:
            async with self._actor_unit_of_work_factory(context) as unit:
                raw = await unit.session.scalar(
                    text("SELECT app_private.request_manual_billing_reconciliation(:org,:reason,:key)"),
                    {"org": organization_id, "reason": reason.value, "key": key_digest},
                )
                result = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(result, dict):
                    raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
                _raise_public_error(result)
                run_id = UUID(str(result["run_id"]))
                await unit.commit()
                return run_id
        except BillingOperationError:
            raise
        except (KeyError, ValueError) as error:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN) from error
        except SQLAlchemyError as error:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE) from error


class PostgresBillingReconciliationLeaseRepository:
    """Réservations à expiration basées sur l'horloge PostgreSQL, sans accès direct aux tables."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def claim(self) -> ReconciliationLease | None:
        async with self._sessions.begin() as session:
            result = await session.execute(text("SELECT * FROM app_private.claim_billing_reconciliation_run()"))
            row = result.mappings().one_or_none()
            if row is None:
                return None
            run_id, token, organization_id = row["run_id"], row["lease_token"], row["organization_id"]
            if not isinstance(run_id, UUID) or not isinstance(token, UUID):
                raise RuntimeError("billing_reconciliation_invalid_lease")
            if organization_id is not None and not isinstance(organization_id, UUID):
                raise RuntimeError("billing_reconciliation_invalid_lease_scope")
            return ReconciliationLease(run_id, token, organization_id)

    async def renew(self, *, lease: ReconciliationLease) -> bool:
        async with self._sessions.begin() as session:
            result = await session.scalar(
                text("SELECT app_private.renew_billing_reconciliation_run(:run,:token)"),
                {"run": lease.run_id, "token": lease.token},
            )
        return result is True

    async def release(self, *, lease: ReconciliationLease) -> bool:
        async with self._sessions.begin() as session:
            result = await session.scalar(
                text("SELECT app_private.release_billing_reconciliation_run(:run,:token)"),
                {"run": lease.run_id, "token": lease.token},
            )
        return result is True

    async def read_next(self, *, lease: ReconciliationLease) -> ReconciliationRead:
        async with self._sessions.begin() as session:
            raw = await session.scalar(
                text("SELECT app_private.read_billing_reconciliation_candidate(:run,:token)"),
                {"run": lease.run_id, "token": lease.token},
            )
        value = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(value, dict):
            raise RuntimeError("billing_reconciliation_invalid_candidate")
        try:
            status = ReconciliationReadStatus(value["status"])
            if status is not ReconciliationReadStatus.CANDIDATE:
                return ReconciliationRead(status)
            if not isinstance(value["cancel_at_period_end"], bool) or not isinstance(value["local_version"], int):
                raise ValueError("invalid candidate types")
            snapshot = NormalizedSubscriptionSnapshot(
                provider_subscription_reference=str(value["subscription_reference"]),
                provider_customer_reference=str(value["customer_reference"]),
                provider_price_reference=str(value["price_reference"]),
                state=SubscriptionState(value["state"]),
                currency=CurrencyCode(value["currency"]),
                period=BillingPeriod(
                    datetime.fromisoformat(value["period_start"]), datetime.fromisoformat(value["period_end"])
                ),
                cancel_at_period_end=value["cancel_at_period_end"],
                provider_updated_at=datetime.fromisoformat(value["provider_updated_at"]),
            )
            candidate = ReconciliationCandidate(
                UUID(value["run_id"]),
                UUID(value["organization_id"]),
                UUID(value["subscription_id"]),
                value["local_version"],
                snapshot,
            )
            return ReconciliationRead(status, candidate)
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("billing_reconciliation_invalid_candidate") from error

    async def complete(self, *, lease: ReconciliationLease) -> bool:
        async with self._sessions.begin() as session:
            result = await session.scalar(
                text("SELECT app_private.complete_billing_reconciliation_run(:run,:token)"),
                {"run": lease.run_id, "token": lease.token},
            )
        return result is True

    async def record_and_advance(
        self,
        *,
        lease: ReconciliationLease,
        candidate: ReconciliationCandidate,
        difference: BillingReconciliationDifferenceCode,
    ) -> bool:
        if candidate.run_id != lease.run_id:
            return False
        async with self._sessions.begin() as session:
            result = await session.scalar(
                text(
                    "SELECT app_private.advance_billing_reconciliation_run(:run,:token,:org,:subscription,:version,:code)"
                ),
                {
                    "run": candidate.run_id,
                    "token": lease.token,
                    "org": candidate.organization_id,
                    "subscription": candidate.subscription_id,
                    "version": candidate.local_version,
                    "code": difference.value,
                },
            )
        return result is True


class PostgresBillingReconciliationScheduleRepository:
    """Réserve une fenêtre fermée sans créer de commande financière."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def last_window_end(self, *, kind: ReconciliationScheduleKind) -> datetime | None:
        async with self._sessions.begin() as session:
            result = await session.scalar(
                text("SELECT app_private.last_billing_reconciliation_window_end(:kind)"), {"kind": kind.value}
            )
            if result is None or isinstance(result, datetime):
                return result
            raise RuntimeError("billing_reconciliation_invalid_window")

    async def schedule_window(self, *, window: ReconciliationWindow) -> UUID | None:
        async with self._sessions.begin() as session:
            result = await session.scalar(
                text("SELECT app_private.schedule_billing_reconciliation_window(:kind,:starts_at,:ends_at)"),
                {"kind": window.kind.value, "starts_at": window.starts_at, "ends_at": window.ends_at},
            )
            if result is None or isinstance(result, UUID):
                return result
            raise RuntimeError("billing_reconciliation_invalid_run")
