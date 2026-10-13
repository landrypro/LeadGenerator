"""Cas d'usage P53-06 pour les sessions Checkout et portail internes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from ...domain.billing import BillingErrorCode
from ..errors import BillingOperationError
from ..ports.billing import (
    BillingCommandRepository,
    BillingCommandState,
    BillingProviderGateway,
    BillingReturnTarget,
)
from ..ports.clock import Clock
from ..tenancy import TenantContext

_RECENT_SESSION_WINDOW = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class BillingSessionGrant:
    url: str
    expires_at: datetime


class BillingSessionUseCases:
    def __init__(self, repository: BillingCommandRepository, provider: BillingProviderGateway, clock: Clock) -> None:
        self._repository = repository
        self._provider = provider
        self._clock = clock

    async def create_checkout(
        self,
        *,
        context: TenantContext,
        plan_version_id: UUID,
        idempotency_key: str,
        return_target: BillingReturnTarget,
        authorized: bool,
        session_issued_at: datetime | None,
    ) -> BillingSessionGrant:
        now = self._clock.now()
        self._require_recent_authorization(authorized, session_issued_at, now)
        preparation = await self._repository.prepare_checkout(
            context=context,
            command_id=uuid4(),
            plan_version_id=plan_version_id,
            idempotency_key_digest=_digest(idempotency_key),
            request_fingerprint=_fingerprint("checkout", str(plan_version_id), return_target.value),
            now=now,
        )
        self._require_known_state(preparation.state)
        try:
            session = await self._provider.create_checkout(
                command=preparation.command,
                idempotency_key=f"checkout:{preparation.command_id}",
            )
        except BillingOperationError as error:
            await self._record_provider_failure(context, preparation.command_id, error)
            raise
        await self._repository.complete_checkout(context=context, preparation=preparation, session=session)
        return BillingSessionGrant(session.checkout_url, session.expires_at)

    async def create_portal(
        self,
        *,
        context: TenantContext,
        idempotency_key: str,
        return_target: BillingReturnTarget,
        authorized: bool,
        session_issued_at: datetime | None,
    ) -> BillingSessionGrant:
        now = self._clock.now()
        self._require_recent_authorization(authorized, session_issued_at, now)
        preparation = await self._repository.prepare_portal(
            context=context,
            command_id=uuid4(),
            idempotency_key_digest=_digest(idempotency_key),
            request_fingerprint=_fingerprint("portal", return_target.value),
            now=now,
        )
        self._require_known_state(preparation.state)
        try:
            session = await self._provider.create_portal_session(
                command=preparation.command,
                idempotency_key=f"portal:{preparation.command_id}",
            )
        except BillingOperationError as error:
            await self._record_provider_failure(context, preparation.command_id, error)
            raise
        await self._repository.complete_portal(context=context, preparation=preparation, session=session)
        return BillingSessionGrant(session.portal_url, session.expires_at)

    @staticmethod
    def _require_recent_authorization(authorized: bool, issued_at: datetime | None, now: datetime) -> None:
        if (
            not authorized
            or issued_at is None
            or issued_at.tzinfo is None
            or issued_at > now
            or now - issued_at > _RECENT_SESSION_WINDOW
        ):
            raise BillingOperationError(BillingErrorCode.CAPABILITY_REQUIRED)

    @staticmethod
    def _require_known_state(state: BillingCommandState) -> None:
        if state is BillingCommandState.UNKNOWN:
            raise BillingOperationError(BillingErrorCode.RECONCILIATION_REQUIRED)

    async def _record_provider_failure(
        self, context: TenantContext, command_id: UUID, error: BillingOperationError
    ) -> None:
        if error.code is BillingErrorCode.RECONCILIATION_REQUIRED:
            await self._repository.mark_unknown(context=context, command_id=command_id)
        else:
            await self._repository.mark_failed(context=context, command_id=command_id, reason=error.code)


def _digest(value: str) -> str:
    if not 1 <= len(value) <= 128 or any(ord(character) < 33 or ord(character) > 126 for character in value):
        raise ValueError("Idempotency-Key est invalide.")
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _fingerprint(*values: str) -> str:
    payload = json.dumps(values, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()
