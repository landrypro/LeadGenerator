"""Runtime borné d'IMP-A4 pour l'admission et l'effet Automation."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.tenancy import TenantContext
from ...domain.prospect import ProspectView
from .job_queue import ClaimedJob, _set_tenant
from .prospect_repository import SqlAlchemyProspectRepository


class AutomationAdmissionConflict(RuntimeError):
    """Une clé Automation est réutilisée avec une charge différente."""


class AutomationAdmissionBlocked(RuntimeError):
    """Les gardes Automation ferment l'admission avant tout effet."""


@dataclass(frozen=True, slots=True)
class AutomatedProspectOutcome:
    prospect: ProspectView
    admission_id: UUID
    job_id: UUID
    state: str
    replayed: bool


class AutomationRuntime:
    """Appelle exclusivement les commandes SQL bornées créées par IMP-A4."""

    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], *, global_enabled: bool, idempotency_secret: bytes
    ) -> None:
        if len(idempotency_secret) < 32:
            raise ValueError("La clé d'idempotence Automation est invalide.")
        self._sessions = sessions
        self._global_enabled = global_enabled
        self._secret = idempotency_secret

    async def admit_manual(
        self,
        *,
        context: TenantContext,
        internal_alias: str,
        requested_membership_id: UUID,
        assigned_membership_id: UUID,
        idempotency_key: str,
    ) -> AutomatedProspectOutcome:
        if not 1 <= len(idempotency_key) <= 128:
            raise ValueError("La clé d'idempotence est invalide.")
        alias = internal_alias.strip()
        if not alias:
            raise ValueError("Le nom interne du prospect est obligatoire.")
        admission_digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        fingerprint = _fingerprint(
            {
                "internal_alias": alias,
                "requested_membership_id": str(requested_membership_id),
                "assigned_membership_id": str(assigned_membership_id),
                "job_type": "automation_new_prospect_prepare",
                "schema_version": 1,
            }
        )
        job_digest = hmac.new(self._secret, idempotency_key.encode("utf-8"), hashlib.sha256).hexdigest()
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            value = await session.scalar(
                text(
                    """
                    SELECT app_private.admit_manual_new_prospect_automation(
                      :alias, :membership_id, :assigned_membership_id, :admission_digest,
                      :fingerprint, :job_digest, :correlation_id, :global_enabled, :request_id
                    )
                    """
                ),
                {
                    "alias": alias,
                    "membership_id": requested_membership_id,
                    "assigned_membership_id": assigned_membership_id,
                    "admission_digest": admission_digest,
                    "fingerprint": fingerprint,
                    "job_digest": job_digest,
                    "correlation_id": UUID(context.request_id.removeprefix("req-"))
                    if _is_uuid(context.request_id.removeprefix("req-"))
                    else uuid4(),
                    "global_enabled": self._global_enabled,
                    "request_id": context.request_id,
                },
            )
            payload = _json(value)
            code = str(payload.get("code", ""))
            if code == "idempotency_conflict":
                raise AutomationAdmissionConflict
            if code != "accepted":
                raise AutomationAdmissionBlocked(code or "automation_disabled")
            prospect_id = UUID(str(payload["prospect_id"]))
            prospect = await SqlAlchemyProspectRepository(session).get(prospect_id)
            if prospect is None:
                raise RuntimeError("Le prospect admis est introuvable.")
            return AutomatedProspectOutcome(
                prospect=prospect,
                admission_id=UUID(str(payload["admission_id"])),
                job_id=UUID(str(payload["job_id"])),
                state=str(payload["state"]),
                replayed=bool(payload.get("replayed", False)),
            )

    async def prepare(self, claim: ClaimedJob, context: TenantContext) -> str:
        if claim.subject_type != "prospect":
            raise ValueError("invalid_contract")
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            value = await session.scalar(
                text(
                    """
                    SELECT app_private.prepare_automation_new_prospect_task(
                      :job_id, :prospect_id, :global_enabled, :request_id
                    )
                    """
                ),
                {
                    "job_id": claim.id,
                    "prospect_id": claim.subject_id,
                    "global_enabled": self._global_enabled,
                    "request_id": context.request_id,
                },
            )
            payload = _json(value)
            return str(payload.get("result_code", "invalid_contract"))

    async def cancel(self, claim: ClaimedJob, context: TenantContext) -> None:
        if claim.type != "automation_new_prospect_prepare":
            return
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            await session.execute(
                text(
                    """
                    UPDATE automation_admissions
                    SET state = 'cancelled', result_code = 'cancelled', completed_at = clock_timestamp(),
                        updated_at = clock_timestamp()
                    WHERE job_id = :job_id AND organization_id = :organization_id
                      AND state = 'ready_to_prepare'
                    """
                ),
                {"job_id": claim.id, "organization_id": context.organization_id},
            )


def _fingerprint(value: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _json(value: Any) -> dict[str, object]:
    return dict(json.loads(value) if isinstance(value, str) else value)


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True
