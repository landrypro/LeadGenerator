"""Attributions temporaires, auditables et exclusivement sandbox."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from ...domain.audit import AuditAction
from ...domain.billing import BillingErrorCode, ManualBillingGrantReasonCode
from ..audit_events import platform_audit_event
from ..errors import BillingOperationError, InsufficientCapability, ManualBillingGrantUnavailable
from ..ports.clock import Clock
from ..ports.manual_billing_grants import (
    ManualBillingGrantAuditedUnitOfWorkFactory,
    ManualBillingGrantMutationCode,
    ManualBillingGrantOption,
    ManualBillingGrantView,
)
from ..tenancy import ActorContext

_RECENT_SESSION_WINDOW = timedelta(minutes=15)
_MAX_DURATION_DAYS = 31


@dataclass(frozen=True, slots=True)
class ProposeManualBillingGrantCommand:
    organization_id: UUID
    plan_version_id: UUID
    reason_code: ManualBillingGrantReasonCode
    duration_days: int

    def __post_init__(self) -> None:
        if not 1 <= self.duration_days <= _MAX_DURATION_DAYS:
            raise ValueError(f"La durée doit être comprise entre 1 et {_MAX_DURATION_DAYS} jours.")


class ManualBillingGrantUseCases:
    """Ne s'instancie que lorsque la sandbox Stripe est explicitement active."""

    def __init__(
        self,
        factory: ManualBillingGrantAuditedUnitOfWorkFactory,
        clock: Clock,
        *,
        sandbox_enabled: bool,
    ) -> None:
        self._factory = factory
        self._clock = clock
        self._sandbox_enabled = sandbox_enabled

    async def list_options(
        self, *, context: ActorContext, has_platform_capability: bool, session_issued_at: datetime | None
    ) -> tuple[ManualBillingGrantOption, ...]:
        now = self._clock.now()
        self._require_authorized(has_platform_capability, session_issued_at, now)
        async with self._factory(context) as unit:
            return await unit.mutations.list_options(now=now)

    async def propose(
        self,
        *,
        context: ActorContext,
        command: ProposeManualBillingGrantCommand,
        idempotency_key: str,
        has_platform_capability: bool,
        session_issued_at: datetime | None,
    ) -> ManualBillingGrantView:
        now = self._clock.now()
        self._require_authorized(has_platform_capability, session_issued_at, now)
        async with self._factory(context) as unit:
            result = await unit.mutations.propose(
                grant_id=uuid4(),
                operation_id=uuid4(),
                idempotency_key_digest=_digest(idempotency_key),
                request_fingerprint=_fingerprint(
                    "propose",
                    str(command.organization_id),
                    str(command.plan_version_id),
                    command.reason_code.value,
                    str(command.duration_days),
                ),
                organization_id=command.organization_id,
                plan_version_id=command.plan_version_id,
                reason_code=command.reason_code,
                duration_days=command.duration_days,
                now=now,
            )
            grant = _grant_or_raise(result.code, result.grant, result.current_version)
            if result.code is ManualBillingGrantMutationCode.REPLAYED:
                return grant
            await unit.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.BILLING_MANUAL_GRANT_PROPOSED,
                    grant.id,
                    {
                        "organization_id": grant.organization_id,
                        "plan_version_id": grant.plan_version_id,
                        "reason_code": grant.reason_code.value,
                        "duration_days": grant.duration_days,
                        "state": grant.state.value,
                    },
                    organization_id=grant.organization_id,
                )
            )
            await unit.commit()
            return grant

    async def approve(
        self,
        *,
        context: ActorContext,
        grant_id: UUID,
        expected_version: int,
        idempotency_key: str,
        has_platform_capability: bool,
        session_issued_at: datetime | None,
    ) -> ManualBillingGrantView:
        now = self._clock.now()
        self._require_authorized(has_platform_capability, session_issued_at, now)
        if expected_version < 1:
            raise ValueError("La version attendue doit être positive.")
        async with self._factory(context) as unit:
            result = await unit.mutations.approve(
                grant_id=grant_id,
                operation_id=uuid4(),
                idempotency_key_digest=_digest(idempotency_key),
                request_fingerprint=_fingerprint("approve", str(grant_id), str(expected_version)),
                expected_version=expected_version,
                now=now,
            )
            grant = _grant_or_raise(result.code, result.grant, result.current_version)
            if result.code is ManualBillingGrantMutationCode.REPLAYED:
                return grant
            await unit.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.BILLING_MANUAL_GRANT_APPROVED,
                    grant.id,
                    {
                        "organization_id": grant.organization_id,
                        "plan_version_id": grant.plan_version_id,
                        "reason_code": grant.reason_code.value,
                        "duration_days": grant.duration_days,
                        "state": grant.state.value,
                        "version": grant.version,
                    },
                    organization_id=grant.organization_id,
                )
            )
            await unit.commit()
            return grant

    async def revoke(
        self,
        *,
        context: ActorContext,
        grant_id: UUID,
        expected_version: int,
        idempotency_key: str,
        has_platform_capability: bool,
        session_issued_at: datetime | None,
    ) -> ManualBillingGrantView:
        now = self._clock.now()
        self._require_authorized(has_platform_capability, session_issued_at, now)
        if expected_version < 1:
            raise ValueError("La version attendue doit être positive.")
        async with self._factory(context) as unit:
            result = await unit.mutations.revoke(
                grant_id=grant_id,
                operation_id=uuid4(),
                idempotency_key_digest=_digest(idempotency_key),
                request_fingerprint=_fingerprint("revoke", str(grant_id), str(expected_version)),
                expected_version=expected_version,
                now=now,
            )
            grant = _grant_or_raise(result.code, result.grant, result.current_version)
            if result.code is ManualBillingGrantMutationCode.REPLAYED:
                return grant
            await unit.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.BILLING_MANUAL_GRANT_REVOKED,
                    grant.id,
                    {
                        "organization_id": grant.organization_id,
                        "plan_version_id": grant.plan_version_id,
                        "reason_code": grant.reason_code.value,
                        "state": grant.state.value,
                        "version": grant.version,
                    },
                    organization_id=grant.organization_id,
                )
            )
            await unit.commit()
            return grant

    def _require_authorized(
        self, has_platform_capability: bool, session_issued_at: datetime | None, now: datetime
    ) -> None:
        if not self._sandbox_enabled:
            raise BillingOperationError(BillingErrorCode.PROVIDER_DISABLED)
        if (
            not has_platform_capability
            or session_issued_at is None
            or session_issued_at.tzinfo is None
            or session_issued_at > now
            or now - session_issued_at > _RECENT_SESSION_WINDOW
        ):
            raise InsufficientCapability


def _grant_or_raise(
    code: ManualBillingGrantMutationCode,
    grant: ManualBillingGrantView | None,
    current_version: int | None,
) -> ManualBillingGrantView:
    if (
        code
        in {
            ManualBillingGrantMutationCode.CREATED,
            ManualBillingGrantMutationCode.APPROVED,
            ManualBillingGrantMutationCode.REVOKED,
            ManualBillingGrantMutationCode.REPLAYED,
        }
        and grant is not None
    ):
        return grant
    if code is ManualBillingGrantMutationCode.NOT_FOUND:
        raise BillingOperationError(BillingErrorCode.MANUAL_GRANT_NOT_FOUND)
    if code is ManualBillingGrantMutationCode.CONFLICT:
        raise BillingOperationError(BillingErrorCode.MANUAL_GRANT_CONFLICT)
    if code is ManualBillingGrantMutationCode.VERSION_CONFLICT:
        del current_version
        raise BillingOperationError(BillingErrorCode.VERSION_CONFLICT)
    if code is ManualBillingGrantMutationCode.APPROVAL_REQUIRED:
        raise BillingOperationError(BillingErrorCode.MANUAL_GRANT_APPROVAL_REQUIRED)
    if code is ManualBillingGrantMutationCode.INVALID_STATE:
        raise BillingOperationError(BillingErrorCode.MANUAL_GRANT_INVALID_STATE)
    if code is ManualBillingGrantMutationCode.CATALOG_VERSION_UNAVAILABLE:
        raise BillingOperationError(BillingErrorCode.CATALOG_VERSION_UNAVAILABLE)
    if code is ManualBillingGrantMutationCode.COMMAND_CONFLICT:
        raise BillingOperationError(BillingErrorCode.COMMAND_CONFLICT)
    raise ManualBillingGrantUnavailable


def _digest(value: str) -> str:
    if not 1 <= len(value) <= 128 or any(ord(character) < 33 or ord(character) > 126 for character in value):
        raise ValueError("Idempotency-Key est invalide.")
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _fingerprint(*values: str) -> str:
    payload = json.dumps(values, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()
