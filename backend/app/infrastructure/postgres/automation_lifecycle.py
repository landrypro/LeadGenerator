"""Transitions de cycle de vie Automation, sans admission ni effet CRM."""

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

LifecycleCommand = Literal["activate", "suspend", "resume"]


class AutomationLifecycleUnavailable(RuntimeError):
    """La transition ne peut pas être persistée de façon sûre."""


class AutomationLifecycleDisabled(RuntimeError):
    """Le flag global ferme les commandes de cycle de vie."""


class AutomationLifecycleRejected(RuntimeError):
    """Une précondition métier de transition n'est pas satisfaite."""


class AutomationLifecycleVersionConflict(RuntimeError):
    """La version attendue ne correspond plus au Playbook."""


@dataclass(frozen=True, slots=True)
class AutomationLifecycleOutcome:
    playbook_code: str
    command: LifecycleCommand
    state: str
    prepare_enabled: bool
    suspension_generation: int
    version: int
    correlation_id: UUID
    replayed: bool


class AutomationPlaybookLifecycle:
    """Exécute uniquement les changements d'état versionnés des Playbooks.

    Aucune de ces commandes ne crée une admission, un job, un prospect, une tâche
    ou une communication. L'activation ne devient possible qu'avec un Prévol
    complet, frais, non vide et identique à l'état courant.
    """

    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], *, global_enabled: bool, idempotency_secret: bytes
    ) -> None:
        if len(idempotency_secret) < 32:
            raise ValueError("La clé d'idempotence Automation est invalide.")
        self._sessions = sessions
        self._global_enabled = global_enabled
        self._secret = idempotency_secret

    async def transition(
        self,
        *,
        context: TenantContext,
        playbook_code: str,
        membership_id: UUID,
        command: LifecycleCommand,
        expected_version: int,
        idempotency_key: str,
        reason_code: str | None = None,
    ) -> AutomationLifecycleOutcome:
        if command not in {"activate", "suspend", "resume"}:
            raise ValueError("La commande Automation est invalide.")
        if expected_version < 1:
            raise ValueError("La version attendue est invalide.")
        if not 1 <= len(idempotency_key) <= 128:
            raise ValueError("La clé d'idempotence est invalide.")
        if not self._global_enabled:
            raise AutomationLifecycleDisabled
        correlation_id = _correlation_id(
            self._secret,
            {
                "organization_id": str(context.organization_id),
                "membership_id": str(membership_id),
                "playbook_code": playbook_code,
                "command": command,
                "expected_version": expected_version,
                "reason_code": reason_code,
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
                        SELECT app_private.transition_automation_playbook(
                          :playbook_code, :command, :membership_id, :expected_version,
                          :correlation_id, :reason_code, :request_id
                        )
                        """
                    ),
                    {
                        "playbook_code": playbook_code,
                        "command": command,
                        "membership_id": membership_id,
                        "expected_version": expected_version,
                        "correlation_id": correlation_id,
                        "reason_code": reason_code,
                        "request_id": context.request_id,
                    },
                )
        except SQLAlchemyError as error:
            raise AutomationLifecycleUnavailable from error
        payload = _json(value)
        code = str(payload.get("code", ""))
        if code == "version_conflict":
            raise AutomationLifecycleVersionConflict
        if code != "completed":
            raise AutomationLifecycleRejected(code or "transition_rejected")
        return AutomationLifecycleOutcome(
            playbook_code=str(payload["playbook_code"]),
            command=command,
            state=str(payload["state"]),
            prepare_enabled=bool(payload["prepare_enabled"]),
            suspension_generation=int(payload["suspension_generation"]),
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
