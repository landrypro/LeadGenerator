"""Prévol Automation persistant, borné et sans effet CRM."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.tenancy import TenantContext


class AutomationPreflightUnavailable(RuntimeError):
    """Le Prévol ne peut pas être enregistré de façon sûre."""


class AutomationPreflightDisabled(RuntimeError):
    """Le flag global ferme le Prévol hors environnement autorisé."""


class AutomationPreflightNotConfigured(RuntimeError):
    """Aucune version de Playbook ne peut être prévolée."""


class AutomationPreflightRejected(RuntimeError):
    """Le serveur a refusé le Prévol avant toute écriture métier."""


@dataclass(frozen=True, slots=True)
class AutomationPreflightOutcome:
    id: UUID
    playbook_code: str
    ruleset_version: str
    state: str
    correlation_id: UUID
    subject_count: int
    green_count: int
    yellow_count: int
    red_count: int
    to_verify_count: int
    created_at: str
    updated_at: str
    expires_at: str
    replayed: bool


class AutomationPreflightRunner:
    """Appelle une procédure SQL qui n'écrit que le journal du Prévol.

    La procédure ne crée ni prospect, ni tâche, ni job, ni message, ni transition
    de pipeline. L'identité et l'organisation sont uniquement issues du contexte
    de session RLS, jamais du navigateur.
    """

    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], *, global_enabled: bool, idempotency_secret: bytes
    ) -> None:
        if len(idempotency_secret) < 32:
            raise ValueError("La clé d'idempotence Automation est invalide.")
        self._sessions = sessions
        self._global_enabled = global_enabled
        self._secret = idempotency_secret

    async def run(
        self,
        *,
        context: TenantContext,
        playbook_code: str,
        membership_id: UUID,
        idempotency_key: str,
    ) -> AutomationPreflightOutcome:
        if not 1 <= len(idempotency_key) <= 128:
            raise ValueError("La clé d'idempotence est invalide.")
        if not self._global_enabled:
            raise AutomationPreflightDisabled
        correlation_id = _correlation_id(
            self._secret,
            {
                "organization_id": str(context.organization_id),
                "membership_id": str(membership_id),
                "playbook_code": playbook_code,
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
                        SELECT app_private.run_automation_preflight(
                          :playbook_code, :membership_id, :correlation_id, :request_id
                        )
                        """
                    ),
                    {
                        "playbook_code": playbook_code,
                        "membership_id": membership_id,
                        "correlation_id": correlation_id,
                        "request_id": context.request_id,
                    },
                )
        except SQLAlchemyError as error:
            raise AutomationPreflightUnavailable from error
        payload = _json(value)
        code = str(payload.get("code", ""))
        if code == "preflight_not_configured":
            raise AutomationPreflightNotConfigured
        if code != "completed":
            raise AutomationPreflightRejected(code or "preflight_rejected")
        return AutomationPreflightOutcome(
            id=UUID(str(payload["id"])),
            playbook_code=str(payload["playbook_code"]),
            ruleset_version=str(payload["ruleset_version"]),
            state=str(payload["state"]),
            correlation_id=UUID(str(payload["correlation_id"])),
            subject_count=int(payload["subject_count"]),
            green_count=int(payload["green_count"]),
            yellow_count=int(payload["yellow_count"]),
            red_count=int(payload["red_count"]),
            to_verify_count=int(payload["to_verify_count"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            expires_at=str(payload["expires_at"]),
            replayed=bool(payload.get("replayed", False)),
        )


async def _set_tenant(session: AsyncSession, context: TenantContext) -> None:
    await session.execute(
        text(
            """
            SELECT
              set_config('app.actor_id', :actor_id, true),
              set_config('app.organization_id', :organization_id, true),
              set_config('app.request_id', :request_id, true)
            """
        ),
        {
            "actor_id": str(context.actor_id),
            "organization_id": str(context.organization_id),
            "request_id": context.request_id,
        },
    )


def _correlation_id(secret: bytes, payload: dict[str, object]) -> UUID:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    digest = bytearray(hmac.new(secret, encoded, hashlib.sha256).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return UUID(bytes=bytes(digest))


def _json(value: Any) -> dict[str, Any]:
    return dict(json.loads(value) if isinstance(value, str) else value or {})
