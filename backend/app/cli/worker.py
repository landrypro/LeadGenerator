"""Standalone Phase 4.2 worker. No HTTP endpoint starts this process."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import signal
from collections.abc import Callable, Coroutine
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from ..application.tenancy import TenantContext
from ..config import Settings
from ..infrastructure.imports import LocalTemporaryCsvFileStore
from ..infrastructure.postgres import PostgresDatabase
from ..infrastructure.postgres.connector_pilot import MetaLeadProcessor
from ..infrastructure.postgres.export_service import (
    ExportForbidden,
    ExportLimitExceeded,
    ExportNotFound,
    ExportService,
)
from ..infrastructure.postgres.job_queue import ClaimedJob, PostgresJobQueue, _set_tenant

LOGGER = logging.getLogger("marketteo.worker")
Handler = Callable[[ClaimedJob, TenantContext, PostgresJobQueue], Coroutine[Any, Any, str]]


class JobCancelled(Exception):
    """Raised by a handler only before an irreversible effect is committed."""


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    database_url: str
    import_temp_directory: str
    idempotency_secret: bytes
    queue_lag_alert_seconds: int = 300
    cleanup_alert_seconds: int = 1800
    meta_settings: Settings | None = None

    @classmethod
    def from_environment(cls) -> WorkerConfig:
        url = os.environ.get("WORKER_DATABASE_URL", "")
        secret = os.environ.get("JOB_IDEMPOTENCY_HMAC_KEY", "").encode("utf-8")
        if not url.startswith("postgresql+asyncpg://prospect_worker:"):
            raise ValueError("WORKER_DATABASE_URL doit utiliser le rôle prospect_worker.")
        if len(secret) < 32:
            raise ValueError("JOB_IDEMPOTENCY_HMAC_KEY doit contenir au moins 32 octets.")
        directory = os.environ.get("IMPORT_TEMP_DIRECTORY", ".runtime/imports")
        if not directory.strip():
            raise ValueError("IMPORT_TEMP_DIRECTORY est obligatoire.")
        queue_lag = int(os.environ.get("JOB_QUEUE_LAG_ALERT_SECONDS", "300"))
        cleanup = int(os.environ.get("JOB_CLEANUP_ALERT_SECONDS", "1800"))
        if queue_lag < 1 or cleanup < 1:
            raise ValueError("Les seuils d'alerte doivent être positifs.")
        return cls(url, directory, secret, queue_lag, cleanup, Settings.from_env())


async def _probe(claim: ClaimedJob, context: TenantContext, queue: PostgresJobQueue) -> str:
    if claim.subject_type != "organization" or claim.subject_id != context.organization_id:
        raise ValueError("invalid_contract")
    if not await queue.heartbeat(claim, context):
        raise RuntimeError("lease_lost")
    if await queue.should_cancel(claim, context):
        raise JobCancelled
    return "ok"


HANDLERS: dict[str, Handler] = {"internal_probe:1": _probe}
SUPPORTED_CONTRACTS = ("internal_probe:1", "export_csv:1", "meta_lead_ads_ingest:1")


class Worker:
    def __init__(self, queue: PostgresJobQueue, database: PostgresDatabase, config: WorkerConfig) -> None:
        self._queue = queue
        self._database = database
        self._config = config
        self._stop = asyncio.Event()
        self._worker_id = _worker_id()
        self._exports = ExportService(database.session_factory, config.import_temp_directory, config.idempotency_secret)
        self._meta = MetaLeadProcessor(database.session_factory, config.meta_settings or Settings())

    def stop(self) -> None:
        self._stop.set()

    async def _authorized(self, claim: ClaimedJob, context: TenantContext) -> bool:
        if claim.actor_membership_id is None:
            return False  # Future system jobs require a registered technical actor and type policy.
        async with self._database.session_factory.begin() as session:
            await _set_tenant(session, context)
            allowed = await session.execute(
                text("""
                    SELECT 1 FROM memberships m
                    JOIN organizations o ON o.id = m.organization_id
                    JOIN users u ON u.id = m.user_id
                    WHERE m.id = :member AND m.user_id = :actor AND m.organization_id = :org
                      AND m.status = 'active' AND o.status = 'active' AND u.status = 'active'
                """),
                {"member": claim.actor_membership_id, "actor": claim.actor_id, "org": claim.organization_id},
            )
            return allowed.scalar_one_or_none() is not None

    async def _heartbeat(self, claim: ClaimedJob, context: TenantContext, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=20)
            except TimeoutError:
                if not await self._queue.heartbeat(claim, context):
                    LOGGER.warning("job_lease_lost job_id=%s", claim.id)
                    stop.set()
                else:
                    await self._queue.touch_worker(self._worker_id)

    async def _fail_export_job(self, claim: ClaimedJob, context: TenantContext, error_code: str) -> None:
        if not await self._queue.fail(claim, context, error_code=error_code):
            return
        if claim.type == "meta_lead_ads_ingest":
            job = await self._queue.inspect_job(claim.id)
            if job is not None and job["status"] == "failed":
                async with self._database.session_factory.begin() as session:
                    await _set_tenant(session, context)
                    await session.execute(
                        text("""
                            UPDATE connector_ingestions
                            SET status = 'failed', error_code = :error_code,
                                finished_at = clock_timestamp(), updated_at = clock_timestamp(), version = version + 1
                            WHERE id = :id AND status IN ('queued', 'running')
                        """),
                        {"id": claim.subject_id, "error_code": str(job["last_error_code"])},
                    )
            return
        if claim.type != "export_csv":
            return
        job = await self._queue.inspect_job(claim.id)
        if job is None:
            return
        if job["status"] == "failed":
            await self._exports.mark_failed(context, claim.subject_id, str(job["last_error_code"]))
        elif job["status"] == "queued":
            await self._exports.mark_queued(context, claim.subject_id)

    async def _cancel_export_job(self, claim: ClaimedJob, context: TenantContext) -> None:
        if await self._queue.cancel_running(claim, context) and claim.type == "export_csv":
            await self._exports.mark_cancelled(context, claim.subject_id)

    async def run_once(self) -> bool:
        claim = await self._queue.claim(SUPPORTED_CONTRACTS)
        if claim is None:
            return False
        context = TenantContext(
            actor_id=claim.actor_id, organization_id=claim.organization_id, request_id=f"job-{claim.id}"
        )
        if not await self._authorized(claim, context):
            await self._fail_export_job(claim, context, "authorization_revoked")
            return True
        if claim.cancel_requested:
            await self._cancel_export_job(claim, context)
            return True
        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(self._heartbeat(claim, context, heartbeat_stop))
        handler = (
            self._exports.generate
            if claim.type == "export_csv"
            else self._meta_ingest
            if claim.type == "meta_lead_ads_ingest"
            else HANDLERS[f"{claim.type}:{claim.schema_version}"]
        )
        handler_task = asyncio.create_task(handler(claim, context, self._queue))
        shutdown_task = asyncio.create_task(self._stop.wait())
        try:
            done, _ = await asyncio.wait(
                {handler_task, heartbeat_task, shutdown_task},
                timeout=1800,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if heartbeat_task in done and handler_task not in done:
                handler_task.cancel()
                with suppress(asyncio.CancelledError):
                    await handler_task
                return True  # The lease is no longer owned by this worker.
            if not done:
                handler_task.cancel()
                with suppress(asyncio.CancelledError):
                    await handler_task
                await self._fail_export_job(claim, context, "timeout")
                return True
            if shutdown_task in done and handler_task not in done:
                try:
                    result = await asyncio.wait_for(handler_task, timeout=30)
                except TimeoutError:
                    handler_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await handler_task
                    return True  # The lease expires and a new worker owns recovery.
            else:
                result = await handler_task
            if not heartbeat_stop.is_set() and not await self._queue.complete(claim, context, result_code=result):
                LOGGER.warning("job_completion_rejected job_id=%s", claim.id)
        except JobCancelled:
            await self._cancel_export_job(claim, context)
        except ValueError:
            await self._fail_export_job(claim, context, "invalid_contract")
        except ExportLimitExceeded:
            await self._fail_export_job(claim, context, "limit_exceeded")
        except (ExportForbidden, ExportNotFound) as error:
            if isinstance(error, ExportForbidden) and await self._queue.should_cancel(claim, context):
                await self._cancel_export_job(claim, context)
            else:
                code = "subject_missing" if isinstance(error, ExportNotFound) else "authorization_revoked"
                await self._fail_export_job(claim, context, code)
        except Exception as error:
            LOGGER.error("job_attempt_failed job_id=%s error_type=%s", claim.id, type(error).__name__)
            await self._fail_export_job(claim, context, "dependency_unavailable")
        finally:
            shutdown_task.cancel()
            with suppress(asyncio.CancelledError):
                await shutdown_task
            heartbeat_stop.set()
            await heartbeat_task
        return True

    async def _meta_ingest(self, claim: ClaimedJob, context: TenantContext, queue: PostgresJobQueue) -> str:
        """Runs the approved pilot after an authorization check in the processor."""
        del queue
        if claim.subject_type != "connector_ingestion":
            raise ValueError("invalid_contract")
        return await self._meta.process(claim.subject_id, context)

    async def run_forever(self) -> None:
        file_store = LocalTemporaryCsvFileStore(self._config.import_temp_directory, max_bytes=10 * 1024 * 1024)
        last_cleanup = 0.0
        last_usage_purge = 0.0
        last_alert_check = 0.0
        loop = asyncio.get_running_loop()
        while not self._stop.is_set():
            await self._queue.touch_worker(self._worker_id)
            if loop.time() - last_cleanup >= 300:
                await self._queue.purge_expired(batch_size=100)
                reconciled = await self._queue.reconcile_usage(batch_size=100)
                if reconciled:
                    LOGGER.warning("usage_attempts_reconciled count=%s", reconciled)
                await file_store.cleanup_expired(max_age_seconds=24 * 3600)
                await self._exports.cleanup(batch_size=100)
                if loop.time() - last_usage_purge >= 24 * 3600:
                    purged_connectors = await self._queue.purge_connector_ingestions(batch_size=100)
                    purged = await self._queue.purge_usage(batch_size=1000)
                    LOGGER.info(
                        "usage_retention_purged events=%s counters=%s connector_references=%s",
                        purged.get("events", 0),
                        purged.get("counters", 0),
                        purged_connectors,
                    )
                    last_usage_purge = loop.time()
                await self._queue.touch_worker(self._worker_id, cleanup_done=True)
                last_cleanup = loop.time()
            if loop.time() - last_alert_check >= 60:
                metrics = await self._queue.metrics(SUPPORTED_CONTRACTS)
                if float(str(metrics["oldest_eligible_seconds"])) > self._config.queue_lag_alert_seconds:
                    LOGGER.warning("job_queue_lag threshold=%s", self._config.queue_lag_alert_seconds)
                if int(str(metrics["failed"])) > 0:
                    LOGGER.warning("job_failed_present count=%s", metrics["failed"])
                if int(str(metrics["unsupported_contracts"])) > 0:
                    LOGGER.warning("job_contract_unsupported count=%s", metrics["unsupported_contracts"])
                if int(str(metrics["expired_leases"])) > 0:
                    LOGGER.warning("job_lease_expired count=%s", metrics["expired_leases"])
                if float(str(metrics["last_cleanup_seconds"])) > self._config.cleanup_alert_seconds:
                    LOGGER.warning("job_cleanup_stale threshold=%s", self._config.cleanup_alert_seconds)
                last_alert_check = loop.time()
            if not await self.run_once():
                with suppress(TimeoutError):
                    await asyncio.wait_for(self._stop.wait(), timeout=2)


def _database(config: WorkerConfig) -> PostgresDatabase:
    return PostgresDatabase(
        config.database_url,
        connect_timeout_seconds=5,
        pool_size=2,
        max_overflow=0,
        pool_timeout_seconds=5,
        statement_timeout_ms=30_000,
    )


def _worker_id() -> str:
    return (os.environ.get("HOSTNAME") or os.environ.get("COMPUTERNAME") or "worker")[:128]


async def _main(args: argparse.Namespace) -> None:
    config = WorkerConfig.from_environment()
    database = _database(config)
    queue = PostgresJobQueue(database.session_factory)
    try:
        if args.command == "enqueue-probe":
            organization_id = UUID(args.organization_id)
            actor_id = UUID(args.actor_id)
            membership_id = UUID(args.membership_id)
            context = TenantContext(actor_id=actor_id, organization_id=organization_id, request_id=f"probe-{uuid4()}")
            async with database.session_factory.begin() as session:
                job_id = await queue.enqueue(
                    session,
                    context=context,
                    job_type="internal_probe",
                    schema_version=1,
                    subject_type="organization",
                    subject_id=organization_id,
                    actor_membership_id=membership_id,
                    idempotency_key=str(uuid4()),
                    fingerprint=hashlib.sha256(f"probe:{organization_id}".encode()).hexdigest(),
                    hmac_secrets={1: config.idempotency_secret},
                    active_secret_version=1,
                )
            print(job_id)
            return
        if args.command == "health":
            if not await queue.worker_healthy(_worker_id()):
                raise RuntimeError("Worker heartbeat absent or stale.")
            return
        if args.command == "status":
            print(json.dumps(await queue.metrics(SUPPORTED_CONTRACTS), sort_keys=True))
            return
        if args.command == "failures":
            print(json.dumps(await queue.failed_jobs(), sort_keys=True))
            return
        if args.command == "inspect":
            print(json.dumps(await queue.inspect_job(UUID(args.job_id)), sort_keys=True))
            return
        if args.command == "replay-probe":
            old_job_id = UUID(args.old_job_id)
            old_job = await queue.inspect_job(old_job_id)
            if old_job is None or old_job["status"] != "failed" or old_job["type"] != "internal_probe":
                raise ValueError("Seul un travail interne échoué peut être relancé ici.")
            organization_id = UUID(str(old_job["organization_id"]))
            actor_id = UUID(args.actor_id)
            membership_id = UUID(args.membership_id)
            context = TenantContext(actor_id=actor_id, organization_id=organization_id, request_id=f"replay-{uuid4()}")
            async with database.session_factory.begin() as session:
                new_job_id = await queue.enqueue(
                    session,
                    context=context,
                    job_type="internal_probe",
                    schema_version=1,
                    subject_type="organization",
                    subject_id=organization_id,
                    actor_membership_id=membership_id,
                    idempotency_key=str(uuid4()),
                    fingerprint=hashlib.sha256(f"probe:{organization_id}".encode()).hexdigest(),
                    hmac_secrets={1: config.idempotency_secret},
                    active_secret_version=1,
                    replay_of_job_id=old_job_id,
                    replay_reason_code=args.reason_code,
                )
            print(new_job_id)
            return
        worker = Worker(queue, database, config)
        loop = asyncio.get_running_loop()
        for name in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                loop.add_signal_handler(name, worker.stop)
        await worker.run_forever()
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Marketteo durable job worker")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run")
    commands.add_parser("health")
    commands.add_parser("status")
    commands.add_parser("failures")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("job_id")
    probe = commands.add_parser("enqueue-probe")
    probe.add_argument("organization_id")
    probe.add_argument("actor_id")
    probe.add_argument("membership_id")
    replay = commands.add_parser("replay-probe")
    replay.add_argument("old_job_id")
    replay.add_argument("actor_id")
    replay.add_argument("membership_id")
    replay.add_argument("reason_code", choices=("dependency_recovered", "authorization_restored", "operator_verified"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
