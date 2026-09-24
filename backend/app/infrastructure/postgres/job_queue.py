"""Durable, tenant-scoped job transitions for the Phase 4.2 worker."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.tenancy import TenantContext

TRANSIENT_ERRORS: Final = frozenset({"dependency_unavailable", "timeout", "lease_lost"})
PERMANENT_ERRORS: Final = frozenset(
    {"authorization_revoked", "subject_missing", "invalid_contract", "provider_rejected", "limit_exceeded"}
)
REPLAY_REASONS: Final = frozenset({"dependency_recovered", "authorization_restored", "operator_verified"})


class JobAdmissionFull(Exception):
    pass


class JobIdempotencyConflict(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    id: UUID
    organization_id: UUID
    type: str
    schema_version: int
    subject_type: str
    subject_id: UUID
    actor_id: UUID
    actor_membership_id: UUID | None
    system_origin: str | None
    attempt_count: int
    max_attempts: int
    owner_token: UUID
    cancel_requested: bool

    @classmethod
    def from_record(cls, record: dict[str, object]) -> ClaimedJob:
        return cls(
            id=UUID(str(record["id"])),
            organization_id=UUID(str(record["organization_id"])),
            type=str(record["type"]),
            schema_version=int(str(record["schema_version"])),
            subject_type=str(record["subject_type"]),
            subject_id=UUID(str(record["subject_id"])),
            actor_id=UUID(str(record["actor_id"])),
            actor_membership_id=(UUID(str(record["actor_membership_id"])) if record["actor_membership_id"] else None),
            system_origin=str(record["system_origin"]) if record["system_origin"] else None,
            attempt_count=int(str(record["attempt_count"])),
            max_attempts=int(str(record["max_attempts"])),
            owner_token=UUID(str(record["owner_token"])),
            cancel_requested=bool(record["cancel_requested"]),
        )


async def _set_tenant(session: AsyncSession, context: TenantContext) -> None:
    await session.execute(
        text("""
            SELECT set_config('app.organization_id', :organization_id, true),
                   set_config('app.actor_id', :actor_id, true),
                   set_config('app.request_id', :request_id, true)
        """),
        {
            "organization_id": str(context.organization_id),
            "actor_id": str(context.actor_id),
            "request_id": context.request_id,
        },
    )


class PostgresJobQueue:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    @staticmethod
    async def enqueue(
        session: AsyncSession,
        *,
        context: TenantContext,
        job_type: str,
        schema_version: int,
        subject_type: str,
        subject_id: UUID,
        actor_membership_id: UUID,
        idempotency_key: str,
        fingerprint: str,
        hmac_secrets: dict[int, bytes],
        active_secret_version: int,
        replay_of_job_id: UUID | None = None,
        replay_reason_code: str | None = None,
    ) -> UUID:
        """Join the caller's business transaction; the caller owns its commit."""
        if not (1 <= len(idempotency_key) <= 128) or not job_type or schema_version < 1:
            raise ValueError("Contrat de travail invalide.")
        if any(ord(character) < 32 or ord(character) == 127 for character in idempotency_key):
            raise ValueError("Clé d'idempotence invalide.")
        if (job_type, schema_version, subject_type) not in {
            ("internal_probe", 1, "organization"),
            ("export_csv", 1, "export_request"),
        }:
            raise ValueError("Type de travail non enregistré.")
        if job_type == "internal_probe" and subject_id != context.organization_id:
            raise ValueError("Sujet du travail invalide.")
        if len(fingerprint) != 64 or any(character not in "0123456789abcdef" for character in fingerprint):
            raise ValueError("Empreinte de requête invalide.")
        if active_secret_version not in hmac_secrets or any(len(value) < 32 for value in hmac_secrets.values()):
            raise ValueError("Secrets d'idempotence invalides.")
        if (replay_of_job_id is None) != (replay_reason_code is None) or (
            replay_reason_code is not None and replay_reason_code not in REPLAY_REASONS
        ):
            raise ValueError("Motif de relance invalide.")
        await _set_tenant(session, context)
        authorized = (
            await session.execute(
                text("""
                    SELECT 1 FROM memberships m
                    JOIN organizations o ON o.id = m.organization_id
                    JOIN users u ON u.id = m.user_id
                    WHERE m.id = :membership_id AND m.user_id = :actor_id
                      AND m.organization_id = :organization_id
                      AND m.status = 'active' AND o.status = 'active' AND u.status = 'active'
                """),
                {
                    "membership_id": actor_membership_id,
                    "actor_id": context.actor_id,
                    "organization_id": context.organization_id,
                },
            )
        ).scalar_one_or_none()
        if authorized is None:
            raise PermissionError("Acteur ou organisation inactif.")
        await session.execute(
            text("""
                INSERT INTO job_scheduler_state (organization_id) VALUES (:organization_id)
                ON CONFLICT (organization_id) DO NOTHING
            """),
            {"organization_id": context.organization_id},
        )
        state = (
            await session.execute(
                text(
                    "SELECT queued_count FROM job_scheduler_state WHERE organization_id = :organization_id FOR UPDATE"
                ),
                {"organization_id": context.organization_id},
            )
        ).one()
        digests = {
            version: hmac.new(secret, idempotency_key.encode("utf-8"), hashlib.sha256).hexdigest()
            for version, secret in hmac_secrets.items()
        }
        replay = (
            await session.execute(
                text("""
                    SELECT id, request_fingerprint FROM jobs
                    WHERE organization_id = :organization_id AND type = :job_type
                      AND idempotency_key_digest = ANY(:digests)
                    LIMIT 1
                """),
                {"organization_id": context.organization_id, "job_type": job_type, "digests": list(digests.values())},
            )
        ).first()
        if replay is not None:
            if replay.request_fingerprint != fingerprint:
                raise JobIdempotencyConflict
            return UUID(str(replay.id))
        if state.queued_count >= 100:
            raise JobAdmissionFull
        if replay_of_job_id is not None:
            replay_allowed = (
                await session.execute(
                    text("""
                        SELECT 1 FROM jobs j JOIN memberships m ON m.id = :membership_id
                        WHERE j.id = :old_id AND j.organization_id = :org
                          AND j.type = :job_type AND j.status = 'failed'
                          AND m.organization_id = :org AND m.user_id = :actor_id
                          AND m.role = 'admin' AND m.status = 'active'
                    """),
                    {
                        "old_id": replay_of_job_id,
                        "org": context.organization_id,
                        "job_type": job_type,
                        "membership_id": actor_membership_id,
                        "actor_id": context.actor_id,
                    },
                )
            ).scalar_one_or_none()
            if replay_allowed is None:
                raise PermissionError("Relance non autorisée.")
        job_id = uuid4()
        await session.execute(
            text("""
                INSERT INTO jobs (id, organization_id, type, schema_version, subject_type, subject_id,
                                  replay_of_job_id, actor_id,
                                  actor_membership_id, idempotency_key_digest, idempotency_key_version,
                                  request_fingerprint, status, created_at, available_at)
                VALUES (:id, :organization_id, :job_type, :schema_version, :subject_type, :subject_id,
                        :replay_of_job_id, :actor_id,
                        :actor_membership_id, :digest, :digest_version, :fingerprint,
                        'queued', clock_timestamp(), clock_timestamp())
            """),
            {
                "id": job_id,
                "organization_id": context.organization_id,
                "job_type": job_type,
                "schema_version": schema_version,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "replay_of_job_id": replay_of_job_id,
                "actor_id": context.actor_id,
                "actor_membership_id": actor_membership_id,
                "digest": digests[active_secret_version],
                "digest_version": active_secret_version,
                "fingerprint": fingerprint,
            },
        )
        await session.execute(
            text("UPDATE job_scheduler_state SET queued_count = queued_count + 1 WHERE organization_id = :org"),
            {"org": context.organization_id},
        )
        await session.execute(
            text("""
                INSERT INTO job_events (id, job_id, organization_id, new_status, reason_code, actor_id, created_at)
                VALUES (:id, :job_id, :organization_id, 'queued', :reason, :actor_id, clock_timestamp())
            """),
            {
                "id": uuid4(),
                "job_id": job_id,
                "organization_id": context.organization_id,
                "reason": f"manual_replay_{replay_reason_code}" if replay_of_job_id is not None else "admitted",
                "actor_id": context.actor_id,
            },
        )
        return job_id

    async def claim(self, supported: tuple[str, ...]) -> ClaimedJob | None:
        if not supported:
            return None
        async with self._sessions.begin() as session:
            record = (
                await session.execute(text("SELECT app_private.claim_job(:supported)"), {"supported": list(supported)})
            ).scalar_one_or_none()
        if record is None:
            return None
        return ClaimedJob.from_record(json.loads(record) if isinstance(record, str) else record)

    async def heartbeat(self, claim: ClaimedJob, context: TenantContext) -> bool:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            result = await session.execute(
                text("""
                    UPDATE jobs SET heartbeat_at = clock_timestamp(), lease_until = clock_timestamp() + interval '90 seconds'
                    WHERE id = :id AND owner_token = :token AND status = 'running'
                      AND lease_until > clock_timestamp()
                    RETURNING id
                """),
                {"id": claim.id, "token": claim.owner_token},
            )
            return result.scalar_one_or_none() is not None

    async def should_cancel(self, claim: ClaimedJob, context: TenantContext) -> bool:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            value = (
                await session.execute(
                    text("""
                        SELECT cancel_requested_at IS NOT NULL FROM jobs
                        WHERE id = :id AND owner_token = :token AND status = 'running'
                    """),
                    {"id": claim.id, "token": claim.owner_token},
                )
            ).scalar_one_or_none()
            return value is True

    async def complete(self, claim: ClaimedJob, context: TenantContext, *, result_code: str = "ok") -> bool:
        if len(result_code) > 64:
            raise ValueError("Code de résultat invalide.")
        return await self._finish(claim, context, state="succeeded", code=result_code, retry=False)

    async def fail(self, claim: ClaimedJob, context: TenantContext, *, error_code: str) -> bool:
        if error_code not in TRANSIENT_ERRORS | PERMANENT_ERRORS:
            raise ValueError("Code d'erreur inconnu.")
        retry = error_code in TRANSIENT_ERRORS and claim.attempt_count < claim.max_attempts
        return await self._finish(claim, context, state="queued" if retry else "failed", code=error_code, retry=retry)

    async def _finish(self, claim: ClaimedJob, context: TenantContext, *, state: str, code: str, retry: bool) -> bool:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            await session.execute(
                text("SELECT organization_id FROM job_scheduler_state WHERE organization_id = :org FOR UPDATE"),
                {"org": claim.organization_id},
            )
            base_delay = 30 if claim.attempt_count == 1 else 120
            delay = base_delay * (80 + claim.id.int % 41) / 100
            terminal_code = "attempts_exhausted" if state == "failed" and code in TRANSIENT_ERRORS else code
            result = await session.execute(
                text("""
                    UPDATE jobs SET status = :state, finished_at = CASE WHEN :retry THEN NULL ELSE clock_timestamp() END,
                      available_at = CASE WHEN :retry THEN clock_timestamp() + (:delay * interval '1 second') ELSE available_at END,
                      expires_at = CASE WHEN :retry THEN NULL ELSE clock_timestamp() +
                        (CASE WHEN :is_failed THEN interval '90 days' ELSE interval '30 days' END) END,
                      lease_until = NULL, owner_token = NULL,
                      last_error_code = CASE WHEN :is_succeeded THEN NULL ELSE :terminal_code END,
                      result_code = CASE WHEN :is_succeeded THEN :code ELSE NULL END,
                      version = version + 1
                    WHERE id = :id AND owner_token = :token AND status = 'running'
                      AND lease_until > clock_timestamp()
                    RETURNING organization_id
                """),
                {
                    "id": claim.id,
                    "token": claim.owner_token,
                    "state": state,
                    "is_failed": state == "failed",
                    "is_succeeded": state == "succeeded",
                    "code": code,
                    "terminal_code": terminal_code,
                    "retry": retry,
                    "delay": delay,
                },
            )
            organization_id = result.scalar_one_or_none()
            if organization_id is None:
                return False
            await session.execute(
                text("""
                    UPDATE job_scheduler_state SET active_count = 0,
                      queued_count = queued_count + CASE WHEN :retry THEN 1 ELSE 0 END
                    WHERE organization_id = :org
                """),
                {"org": organization_id, "retry": retry},
            )
            await session.execute(
                text("""
                    UPDATE job_attempts SET finished_at = clock_timestamp(), result_code = :code
                    WHERE job_id = :id AND attempt_number = :attempt AND owner_token = :token
                """),
                {"id": claim.id, "attempt": claim.attempt_count, "token": claim.owner_token, "code": code},
            )
            await session.execute(
                text("""
                    INSERT INTO job_events (id, job_id, organization_id, old_status, new_status, reason_code, created_at)
                    VALUES (:event_id, :id, :org, 'running', :state, :terminal_code, clock_timestamp())
                """),
                {
                    "event_id": uuid4(),
                    "id": claim.id,
                    "org": organization_id,
                    "state": state,
                    "terminal_code": terminal_code,
                },
            )
            return True

    async def purge_expired(self, *, batch_size: int = 100) -> int:
        async with self._sessions.begin() as session:
            return int(
                (
                    await session.execute(text("SELECT app_private.purge_jobs(:batch)"), {"batch": batch_size})
                ).scalar_one()
            )

    async def touch_worker(self, worker_id: str, *, cleanup_done: bool = False) -> None:
        if not 1 <= len(worker_id) <= 128:
            raise ValueError("Identifiant worker invalide.")
        async with self._sessions.begin() as session:
            await session.execute(
                text("""
                    INSERT INTO worker_heartbeats (worker_id, last_seen_at, last_cleanup_at)
                    VALUES (:worker_id, clock_timestamp(), CASE WHEN :cleanup_done THEN clock_timestamp() ELSE NULL END)
                    ON CONFLICT (worker_id) DO UPDATE SET
                      last_seen_at = EXCLUDED.last_seen_at,
                      last_cleanup_at = CASE WHEN :cleanup_done THEN EXCLUDED.last_seen_at
                                             ELSE worker_heartbeats.last_cleanup_at END
                """),
                {"worker_id": worker_id, "cleanup_done": cleanup_done},
            )

    async def worker_healthy(self, worker_id: str) -> bool:
        async with self._sessions.begin() as session:
            result = await session.execute(
                text("""
                    SELECT 1 FROM worker_heartbeats
                    WHERE worker_id = :worker_id AND last_seen_at > clock_timestamp() - interval '60 seconds'
                """),
                {"worker_id": worker_id},
            )
            return result.scalar_one_or_none() is not None

    async def metrics(self, supported: tuple[str, ...]) -> dict[str, object]:
        async with self._sessions.begin() as session:
            value = (
                await session.execute(
                    text("SELECT app_private.job_metrics(:supported)"), {"supported": list(supported)}
                )
            ).scalar_one()
            return dict(json.loads(value) if isinstance(value, str) else value)

    async def failed_jobs(self, *, limit: int = 50) -> list[dict[str, object]]:
        async with self._sessions.begin() as session:
            value = (
                await session.execute(text("SELECT app_private.failed_jobs(:limit)"), {"limit": limit})
            ).scalar_one()
            return list(json.loads(value) if isinstance(value, str) else value)

    async def inspect_job(self, job_id: UUID) -> dict[str, object] | None:
        async with self._sessions.begin() as session:
            value = (
                await session.execute(text("SELECT app_private.inspect_job(:job_id)"), {"job_id": job_id})
            ).scalar_one_or_none()
            if value is None:
                return None
            return dict(json.loads(value) if isinstance(value, str) else value)

    async def get_status(self, context: TenantContext, job_id: UUID) -> dict[str, object] | None:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            row = (
                (
                    await session.execute(
                        text("""
                        SELECT id, type, status, attempt_count, created_at, finished_at, result_code, last_error_code
                        FROM jobs WHERE id = :id
                    """),
                        {"id": job_id},
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row is not None else None

    async def request_cancel(self, context: TenantContext, job_id: UUID) -> str | None:
        """Internal command; caller must check the future type-specific capability first."""
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            await session.execute(
                text("SELECT organization_id FROM job_scheduler_state WHERE organization_id = :org FOR UPDATE"),
                {"org": context.organization_id},
            )
            row = (
                await session.execute(text("SELECT status FROM jobs WHERE id = :id FOR UPDATE"), {"id": job_id})
            ).first()
            if row is None:
                return None
            if row.status == "queued":
                await session.execute(
                    text("""
                        UPDATE jobs SET status = 'cancelled', finished_at = clock_timestamp(),
                          expires_at = clock_timestamp() + interval '30 days', version = version + 1
                        WHERE id = :id
                    """),
                    {"id": job_id},
                )
                await session.execute(
                    text("UPDATE job_scheduler_state SET queued_count = queued_count - 1 WHERE organization_id = :org"),
                    {"org": context.organization_id},
                )
                await session.execute(
                    text("""
                        INSERT INTO job_events (id, job_id, organization_id, old_status, new_status,
                                                reason_code, actor_id, created_at)
                        VALUES (:event_id, :id, :org, 'queued', 'cancelled', 'cancel_requested', :actor_id, clock_timestamp())
                    """),
                    {"event_id": uuid4(), "id": job_id, "org": context.organization_id, "actor_id": context.actor_id},
                )
                return "cancelled"
            if row.status == "running":
                await session.execute(
                    text("""
                        UPDATE jobs SET cancel_requested_at = COALESCE(cancel_requested_at, clock_timestamp()),
                          version = version + 1 WHERE id = :id
                    """),
                    {"id": job_id},
                )
            return str(row.status)

    async def cancel_running(self, claim: ClaimedJob, context: TenantContext) -> bool:
        async with self._sessions.begin() as session:
            await _set_tenant(session, context)
            await session.execute(
                text("SELECT organization_id FROM job_scheduler_state WHERE organization_id = :org FOR UPDATE"),
                {"org": claim.organization_id},
            )
            job_id = (
                await session.execute(
                    text("""
                        UPDATE jobs SET status = 'cancelled', finished_at = clock_timestamp(),
                          expires_at = clock_timestamp() + interval '30 days', lease_until = NULL,
                          owner_token = NULL, version = version + 1
                        WHERE id = :id AND owner_token = :token AND status = 'running'
                          AND lease_until > clock_timestamp() AND cancel_requested_at IS NOT NULL
                        RETURNING id
                    """),
                    {"id": claim.id, "token": claim.owner_token},
                )
            ).scalar_one_or_none()
            if job_id is None:
                return False
            await session.execute(
                text("UPDATE job_scheduler_state SET active_count = 0 WHERE organization_id = :org"),
                {"org": claim.organization_id},
            )
            await session.execute(
                text("""
                    UPDATE job_attempts SET finished_at = clock_timestamp(), result_code = 'cancelled'
                    WHERE job_id = :id AND attempt_number = :attempt AND owner_token = :token
                """),
                {"id": claim.id, "attempt": claim.attempt_count, "token": claim.owner_token},
            )
            await session.execute(
                text("""
                    INSERT INTO job_events (id, job_id, organization_id, old_status, new_status, reason_code, created_at)
                    VALUES (:event_id, :id, :org, 'running', 'cancelled', 'cancel_requested', clock_timestamp())
                """),
                {"event_id": uuid4(), "id": claim.id, "org": claim.organization_id},
            )
            return True
