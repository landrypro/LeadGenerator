from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.cli import worker as worker_module
from backend.app.cli.worker import Worker, WorkerConfig
from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.job_queue import ClaimedJob, PostgresJobQueue


def _claim(*, job_type: str = "internal_probe", subject_type: str = "organization") -> ClaimedJob:
    organization_id = uuid4()
    return ClaimedJob(
        id=uuid4(),
        organization_id=organization_id,
        type=job_type,
        schema_version=1,
        subject_type=subject_type,
        subject_id=organization_id if subject_type == "organization" else uuid4(),
        actor_id=uuid4(),
        actor_membership_id=uuid4(),
        system_origin=None,
        attempt_count=1,
        max_attempts=3,
        owner_token=uuid4(),
        cancel_requested=False,
    )


@pytest.mark.asyncio
async def test_lost_lease_cancels_handler_before_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    claim = _claim()
    queue = MagicMock(spec=PostgresJobQueue)
    queue.claim = AsyncMock(return_value=claim)
    queue.complete = AsyncMock(return_value=True)
    database = MagicMock(spec=PostgresDatabase)
    runner = Worker(queue, database, WorkerConfig("unused", "unused", b"x" * 32))
    monkeypatch.setattr(runner, "_authorized", AsyncMock(return_value=True))
    handler_cancelled = asyncio.Event()

    async def handler(*_args: object) -> str:
        try:
            await asyncio.Event().wait()
        finally:
            handler_cancelled.set()
        return "ok"

    async def lose_lease(_claim: ClaimedJob, _context: object, stop: asyncio.Event) -> None:
        stop.set()

    monkeypatch.setitem(worker_module.HANDLERS, "internal_probe:1", handler)
    monkeypatch.setattr(runner, "_heartbeat", lose_lease)

    assert await asyncio.wait_for(runner.run_once(), timeout=2)
    assert handler_cancelled.is_set()
    queue.complete.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("accepted", "job_status", "expected_method"),
    [(False, "failed", None), (True, "queued", "mark_queued"), (True, "failed", "mark_failed")],
)
async def test_export_failure_follows_committed_job_state(
    accepted: bool, job_status: str, expected_method: str | None
) -> None:
    organization_id, actor_id = uuid4(), uuid4()
    claim = ClaimedJob(
        id=uuid4(),
        organization_id=organization_id,
        type="export_csv",
        schema_version=1,
        subject_type="export_request",
        subject_id=uuid4(),
        actor_id=actor_id,
        actor_membership_id=uuid4(),
        system_origin=None,
        attempt_count=1,
        max_attempts=3,
        owner_token=uuid4(),
        cancel_requested=False,
    )
    queue = MagicMock(spec=PostgresJobQueue)
    queue.fail = AsyncMock(return_value=accepted)
    queue.inspect_job = AsyncMock(return_value={"status": job_status, "last_error_code": "attempts_exhausted"})
    database = MagicMock(spec=PostgresDatabase)
    runner = Worker(queue, database, WorkerConfig("unused", "unused", b"x" * 32))
    runner._exports.mark_queued = AsyncMock()
    runner._exports.mark_failed = AsyncMock()

    await runner._fail_export_job(
        claim,
        worker_module.TenantContext(actor_id=actor_id, organization_id=organization_id, request_id="test"),
        "timeout",
    )

    if expected_method is None:
        queue.inspect_job.assert_not_awaited()
        runner._exports.mark_queued.assert_not_awaited()
        runner._exports.mark_failed.assert_not_awaited()
    else:
        getattr(runner._exports, expected_method).assert_awaited_once()


@pytest.mark.asyncio
async def test_imp_a6_revoked_authorization_closes_automation_before_failing_job() -> None:
    claim = _claim(job_type="automation_new_prospect_prepare", subject_type="prospect")
    queue = MagicMock(spec=PostgresJobQueue)
    queue.claim = AsyncMock(return_value=claim)
    queue.fail = AsyncMock(return_value=True)
    database = MagicMock(spec=PostgresDatabase)
    runner = Worker(queue, database, WorkerConfig("unused", "unused", b"x" * 32))
    runner._authorized = AsyncMock(return_value=False)
    runner._automation.block = AsyncMock()

    assert await runner.run_once() is True

    runner._automation.block.assert_awaited_once()
    assert runner._automation.block.await_args.kwargs == {"reason_code": "authorization_revoked"}
    queue.fail.assert_awaited_once()
    assert queue.fail.await_args.kwargs == {"error_code": "authorization_revoked"}


@pytest.mark.asyncio
async def test_imp_a6_dependency_failure_is_closed_without_exposing_fault_hook() -> None:
    claim = _claim(job_type="automation_new_prospect_prepare", subject_type="prospect")
    queue = MagicMock(spec=PostgresJobQueue)
    queue.claim = AsyncMock(return_value=claim)
    queue.fail = AsyncMock(return_value=True)
    database = MagicMock(spec=PostgresDatabase)
    runner = Worker(queue, database, WorkerConfig("unused", "unused", b"x" * 32))
    runner._authorized = AsyncMock(return_value=True)
    runner._automation.prepare = AsyncMock(side_effect=ConnectionError("synthetic dependency failure"))

    assert await runner.run_once() is True

    queue.fail.assert_awaited_once()
    assert queue.fail.await_args.kwargs == {"error_code": "dependency_unavailable"}
    queue.complete.assert_not_awaited()
