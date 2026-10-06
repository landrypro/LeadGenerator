"""Résolution explicite et sans effet CRM des exceptions Automation."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.tenancy import TenantContext
from .automation_preflight import _set_tenant

ExceptionCommand = Literal["claim", "resolve", "abandon", "reconcile"]


class AutomationExceptionUnavailable(RuntimeError):
    """La transition d'exception ne peut pas être persistée."""


class AutomationExceptionRejected(RuntimeError):
    """Une précondition de prise en charge ou résolution échoue."""


class AutomationExceptionVersionConflict(RuntimeError):
    """L'exception a changé depuis sa dernière lecture."""


@dataclass(frozen=True, slots=True)
class AutomationExceptionOutcome:
    id: UUID
    command: ExceptionCommand
    state: str
    assigned_membership_id: UUID | None
    resolution_code: str | None
    version: int
    correlation_id: UUID
    replayed: bool


class AutomationExceptionResolution:
    """Applique les décisions humaines sans admission, retry ou effet externe."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession], *, idempotency_secret: bytes) -> None:
        if len(idempotency_secret) < 32:
            raise ValueError("La clé d'idempotence Automation est invalide.")
        self._sessions = sessions
        self._secret = idempotency_secret

    async def transition(
        self,
        *,
        context: TenantContext,
        exception_id: UUID,
        membership_id: UUID,
        command: ExceptionCommand,
        expected_version: int,
        idempotency_key: str,
        resolution_code: str | None,
        can_manage_organization: bool,
    ) -> AutomationExceptionOutcome:
        if command not in {"claim", "resolve", "abandon", "reconcile"}:
            raise ValueError("La commande d'exception est invalide.")
        if expected_version < 1 or not 1 <= len(idempotency_key) <= 128:
            raise ValueError("La version ou la clé d'idempotence est invalide.")
        correlation_id = _correlation_id(
            self._secret,
            {
                "organization_id": str(context.organization_id),
                "membership_id": str(membership_id),
                "exception_id": str(exception_id),
                "command": command,
                "expected_version": expected_version,
                "resolution_code": resolution_code,
                "idempotency_key": idempotency_key,
                "schema_version": 1,
            },
        )
        try:
            async with self._sessions.begin() as session:
                await _set_tenant(session, context)
                value = await session.scalar(
                    text(
                        """
                        SELECT app_private.transition_automation_exception(
                          :exception_id, :command, :membership_id, :expected_version,
                          :correlation_id, :resolution_code, :can_manage_organization, :request_id
                        )
                        """
                    ),
                    {
                        "exception_id": exception_id,
                        "command": command,
                        "membership_id": membership_id,
                        "expected_version": expected_version,
                        "correlation_id": correlation_id,
                        "resolution_code": resolution_code,
                        "can_manage_organization": can_manage_organization,
                        "request_id": context.request_id,
                    },
                )
        except SQLAlchemyError as error:
            raise AutomationExceptionUnavailable from error
        payload = _json(value)
        code = str(payload.get("code", ""))
        if code == "version_conflict":
            raise AutomationExceptionVersionConflict
        if code != "completed":
            raise AutomationExceptionRejected(code or "exception_transition_rejected")
        assigned = payload.get("assigned_membership_id")
        return AutomationExceptionOutcome(
            id=UUID(str(payload["id"])),
            command=command,
            state=str(payload["state"]),
            assigned_membership_id=UUID(str(assigned)) if assigned else None,
            resolution_code=str(payload["resolution_code"]) if payload.get("resolution_code") else None,
            version=int(payload["version"]),
            correlation_id=UUID(str(payload["correlation_id"])),
            replayed=bool(payload.get("replayed", False)),
        )


def _correlation_id(secret: bytes, payload: dict[str, object]) -> UUID:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    digest = bytearray(hmac.new(secret, encoded, hashlib.sha256).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return UUID(bytes=bytes(digest))


def _json(value: Any) -> dict[str, Any]:
    return dict(json.loads(value) if isinstance(value, str) else value or {})
