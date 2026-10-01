from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.application.tenancy import TenantContext
from backend.app.cli.worker import Worker, WorkerConfig
from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.job_queue import JobAdmissionFull, JobIdempotencyConflict, PostgresJobQueue

pytestmark = pytest.mark.integration


def _database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=2,
        pool_size=2,
        max_overflow=0,
        pool_timeout_seconds=3,
        statement_timeout_ms=10_000,
    )


@pytest.mark.asyncio
async def test_durable_jobs_are_tenant_scoped_idempotent_and_claimed_once() -> None:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    worker_url = os.environ.get("TEST_WORKER_DATABASE_URL", "")
    if not all((app_url, owner_url, worker_url)):
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("Les trois URL PostgreSQL de test sont obligatoires.")
        pytest.skip("PostgreSQL de test et rôle worker requis.")
    app, owner, worker = _database(app_url), _database(owner_url), _database(worker_url)
    app_queue, worker_queue = PostgresJobQueue(app.session_factory), PostgresJobQueue(worker.session_factory)
    ids = {name: uuid4() for name in ("org_a", "org_b", "user_a", "user_b", "member_a", "member_b")}
    now = datetime.now(UTC)
    context_a = TenantContext(actor_id=ids["user_a"], organization_id=ids["org_a"], request_id="job-test-a")
    context_b = TenantContext(actor_id=ids["user_b"], organization_id=ids["org_b"], request_id="job-test-b")
    secret = {1: b"job-test-secret-with-at-least-32-bytes"}

    async def enqueue(
        session: AsyncSession, context: TenantContext, member_id: UUID, key: str, fingerprint: str
    ) -> UUID:
        return await app_queue.enqueue(
            session,
            context=context,
            job_type="internal_probe",
            schema_version=1,
            subject_type="organization",
            subject_id=context.organization_id,
            actor_membership_id=member_id,
            idempotency_key=key,
            fingerprint=fingerprint,
            hmac_secrets=secret,
            active_secret_version=1,
        )

    fingerprint = hashlib.sha256(b"probe").hexdigest()
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("""
                    INSERT INTO users (id, email, email_normalized, display_name, password_hash, status,
                                       created_at, updated_at) VALUES
                      (:user_a, :email_a, :email_a, 'Job A', 'hash', 'active', :now, :now),
                      (:user_b, :email_b, :email_b, 'Job B', 'hash', 'active', :now, :now)
                """),
                {
                    **ids,
                    "email_a": f"job-a-{ids['user_a']}@example.ca",
                    "email_b": f"job-b-{ids['user_b']}@example.ca",
                    "now": now,
                },
            )
            await connection.execute(
                text("""
                    INSERT INTO organizations (id, name, timezone, status, created_by, activated_at,
                                               created_at, updated_at) VALUES
                      (:org_a, 'Job A', 'America/Toronto', 'active', :user_a, :now, :now, :now),
                      (:org_b, 'Job B', 'America/Toronto', 'active', :user_b, :now, :now, :now)
                """),
                {**ids, "now": now},
            )
            await connection.execute(
                text("""
                    INSERT INTO memberships (id, organization_id, user_id, role, created_by, updated_by,
                                             created_at, updated_at, version) VALUES
                      (:member_a, :org_a, :user_a, 'admin', :user_a, :user_a, :now, :now, 1),
                      (:member_b, :org_b, :user_b, 'admin', :user_b, :user_b, :now, :now, 1)
                """),
                {**ids, "now": now},
            )

        async with app.session_factory() as session:
            await session.begin()
            rolled_back = await enqueue(session, context_a, ids["member_a"], "rolled-back", fingerprint)
            await session.rollback()
        assert await worker_queue.claim(("internal_probe:1",)) is None
        async with app.session_factory() as session:
            await session.begin()
            for index in range(100):
                await enqueue(session, context_a, ids["member_a"], f"capacity-{index}", fingerprint)
            with pytest.raises(JobAdmissionFull):
                await enqueue(session, context_a, ids["member_a"], "capacity-overflow", fingerprint)
            await session.rollback()
        assert await worker_queue.claim(("internal_probe:1",)) is None
        async with app.session_factory.begin() as session:
            job_a = await enqueue(session, context_a, ids["member_a"], "first", fingerprint)
        async with app.session_factory.begin() as session:
            replay = await enqueue(session, context_a, ids["member_a"], "first", fingerprint)
        assert replay == job_a
        assert rolled_back != job_a
        with pytest.raises(JobIdempotencyConflict):
            async with app.session_factory.begin() as session:
                await enqueue(session, context_a, ids["member_a"], "first", hashlib.sha256(b"other").hexdigest())
        assert await app_queue.get_status(context_b, job_a) is None

        async with app.session_factory.begin() as session:
            job_b = await enqueue(session, context_b, ids["member_b"], "second", fingerprint)
        with pytest.raises(DBAPIError):
            async with app.session_factory.begin() as session:
                await session.execute(text("SELECT app_private.claim_job(ARRAY['internal_probe:1']::text[])"))
        async with worker.session_factory.begin() as session:
            assert (await session.execute(text("SELECT count(*) FROM jobs"))).scalar_one() == 0
        async with worker.session_factory.begin() as session:
            crm_privileges = (
                (
                    await session.execute(
                        text("""
                            SELECT
                                has_table_privilege(current_user, 'public.prospects', 'SELECT') AS can_select,
                                has_table_privilege(current_user, 'public.prospects', 'INSERT') AS can_insert,
                                has_table_privilege(current_user, 'public.prospects', 'UPDATE') AS can_update,
                                has_table_privilege(current_user, 'public.prospects', 'DELETE') AS can_delete
                        """)
                    )
                )
                .mappings()
                .one()
            )
            # Phase 4.3 grants a tenant-filtered read projection; Phase 4.5 adds creation
            # rights for connector admissions without granting modification rights.
            assert (await session.execute(text("SELECT count(*) FROM prospects"))).scalar_one() == 0
        assert dict(crm_privileges) == {
            "can_select": True,
            "can_insert": True,
            "can_update": False,
            "can_delete": False,
        }
        first, second = await asyncio.gather(
            worker_queue.claim(("internal_probe:1",)), worker_queue.claim(("internal_probe:1",))
        )
        assert first is not None and second is not None
        assert {first.id, second.id} == {job_a, job_b}
        assert await worker_queue.claim(("internal_probe:1",)) is None
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("UPDATE jobs SET lease_until = clock_timestamp() - interval '1 second' WHERE id = :id"),
                {"id": first.id},
            )
        recovered = await worker_queue.claim(("internal_probe:1",))
        assert recovered is not None and recovered.id == first.id
        assert recovered.attempt_count == 2 and recovered.owner_token != first.owner_token
        stale_context = context_a if first.organization_id == ids["org_a"] else context_b
        assert not await worker_queue.complete(first, stale_context)
        for claim in (recovered, second):
            context = context_a if claim.organization_id == ids["org_a"] else context_b
            assert await worker_queue.complete(claim, context)
            assert not await worker_queue.complete(claim, context)
            status = await app_queue.get_status(context, claim.id)
            assert status is not None and status["status"] == "succeeded"

        concurrency_ids: set[UUID] = set()
        for context, member_id in ((context_a, ids["member_a"]), (context_b, ids["member_b"])):
            async with app.session_factory.begin() as session:
                for index in range(10):
                    concurrency_ids.add(await enqueue(session, context, member_id, f"concurrent-{index}", fingerprint))
        claimed_ids: set[UUID] = set()
        for _ in range(10):
            pair = await asyncio.gather(
                worker_queue.claim(("internal_probe:1",)), worker_queue.claim(("internal_probe:1",))
            )
            assert pair[0] is not None and pair[1] is not None
            assert pair[0].organization_id != pair[1].organization_id
            for claim in pair:
                assert claim.id not in claimed_ids
                claimed_ids.add(claim.id)
                context = context_a if claim.organization_id == ids["org_a"] else context_b
                assert await worker_queue.complete(claim, context)
        assert claimed_ids == concurrency_ids

        async with app.session_factory.begin() as session:
            retry_id = await enqueue(session, context_a, ids["member_a"], "retry", fingerprint)
            eligible = await session.scalar(
                text("SELECT available_at <= clock_timestamp() FROM jobs WHERE id = :id"), {"id": retry_id}
            )
            assert eligible is True
        retry_claim = await worker_queue.claim(("internal_probe:1",))
        assert retry_claim is not None and retry_claim.id == retry_id
        assert await worker_queue.fail(retry_claim, context_a, error_code="dependency_unavailable")
        async with owner.engine.begin() as connection:
            first_delay = (
                await connection.execute(
                    text("SELECT EXTRACT(EPOCH FROM available_at - clock_timestamp()) FROM jobs WHERE id = :id"),
                    {"id": retry_id},
                )
            ).scalar_one()
            assert 20 <= float(first_delay) <= 37
            await connection.execute(
                text("UPDATE jobs SET available_at = clock_timestamp() - interval '1 second' WHERE id = :id"),
                {"id": retry_id},
            )
        second_attempt = await worker_queue.claim(("internal_probe:1",))
        assert second_attempt is not None and second_attempt.attempt_count == 2
        assert await worker_queue.fail(second_attempt, context_a, error_code="dependency_unavailable")
        async with owner.engine.begin() as connection:
            second_delay = (
                await connection.execute(
                    text("SELECT EXTRACT(EPOCH FROM available_at - clock_timestamp()) FROM jobs WHERE id = :id"),
                    {"id": retry_id},
                )
            ).scalar_one()
            assert 90 <= float(second_delay) <= 145
            await connection.execute(
                text("UPDATE jobs SET available_at = clock_timestamp() - interval '1 second' WHERE id = :id"),
                {"id": retry_id},
            )
        third_attempt = await worker_queue.claim(("internal_probe:1",))
        assert third_attempt is not None and third_attempt.attempt_count == 3
        assert await worker_queue.complete(third_attempt, context_a)

        async with app.session_factory.begin() as session:
            exhausted_id = await enqueue(session, context_a, ids["member_a"], "exhausted", fingerprint)
        for attempt_number in (1, 2, 3):
            exhausted_claim = await worker_queue.claim(("internal_probe:1",))
            assert exhausted_claim is not None and exhausted_claim.id == exhausted_id
            assert exhausted_claim.attempt_count == attempt_number
            assert await worker_queue.fail(exhausted_claim, context_a, error_code="dependency_unavailable")
            if attempt_number < 3:
                async with owner.engine.begin() as connection:
                    await connection.execute(
                        text("UPDATE jobs SET available_at = clock_timestamp() - interval '1 second' WHERE id = :id"),
                        {"id": exhausted_id},
                    )
        exhausted_status = await app_queue.get_status(context_a, exhausted_id)
        assert exhausted_status is not None and exhausted_status["status"] == "failed"
        assert exhausted_status["last_error_code"] == "attempts_exhausted"

        async with app.session_factory.begin() as session:
            failed_id = await enqueue(session, context_a, ids["member_a"], "permanent", fingerprint)
        failed_claim = await worker_queue.claim(("internal_probe:1",))
        assert failed_claim is not None and failed_claim.id == failed_id
        assert await worker_queue.fail(failed_claim, context_a, error_code="provider_rejected")
        failed_status = await app_queue.get_status(context_a, failed_id)
        assert failed_status is not None and failed_status["status"] == "failed"
        assert any(item["id"] == str(failed_id) for item in await worker_queue.failed_jobs())
        inspection = await worker_queue.inspect_job(failed_id)
        assert inspection is not None and isinstance(inspection["attempts"], list)
        assert len(inspection["attempts"]) == 1

        async with app.session_factory.begin() as session:
            replay_id = await app_queue.enqueue(
                session,
                context=context_a,
                job_type="internal_probe",
                schema_version=1,
                subject_type="organization",
                subject_id=context_a.organization_id,
                actor_membership_id=ids["member_a"],
                idempotency_key="manual-replay",
                fingerprint=fingerprint,
                hmac_secrets=secret,
                active_secret_version=1,
                replay_of_job_id=failed_id,
                replay_reason_code="operator_verified",
            )
        replay_inspection = await worker_queue.inspect_job(replay_id)
        assert replay_inspection is not None and replay_inspection["replay_of_job_id"] == str(failed_id)
        async with owner.engine.begin() as connection:
            replay_reason = (
                await connection.execute(
                    text("SELECT reason_code FROM job_events WHERE job_id = :id"), {"id": replay_id}
                )
            ).scalar_one()
        assert replay_reason == "manual_replay_operator_verified"
        replay_claim = await worker_queue.claim(("internal_probe:1",))
        assert replay_claim is not None and replay_claim.id == replay_id
        assert await worker_queue.complete(replay_claim, context_a)

        async with app.session_factory.begin() as session:
            cancelled_id = await enqueue(session, context_a, ids["member_a"], "cancel-queued", fingerprint)
        assert await app_queue.request_cancel(context_a, cancelled_id) == "cancelled"
        cancelled_status = await app_queue.get_status(context_a, cancelled_id)
        assert cancelled_status is not None and cancelled_status["status"] == "cancelled"
        async with app.session_factory.begin() as session:
            running_id = await enqueue(session, context_a, ids["member_a"], "cancel-running", fingerprint)
        running_claim = await worker_queue.claim(("internal_probe:1",))
        assert running_claim is not None and running_claim.id == running_id
        assert await app_queue.request_cancel(context_a, running_id) == "running"
        assert await worker_queue.should_cancel(running_claim, context_a)
        assert await worker_queue.cancel_running(running_claim, context_a)

        async with app.session_factory.begin() as session:
            revoked_id = await enqueue(session, context_a, ids["member_a"], "revoked", fingerprint)
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("UPDATE memberships SET status = 'disabled' WHERE id = :id"), {"id": ids["member_a"]}
            )
        with pytest.raises(PermissionError):
            async with app.session_factory.begin() as session:
                await enqueue(session, context_a, ids["member_a"], "first", fingerprint)
        runner = Worker(worker_queue, worker, WorkerConfig(worker_url, ".runtime/imports", b"x" * 32))
        assert await runner.run_once()
        revoked_status = await app_queue.get_status(context_a, revoked_id)
        assert revoked_status is not None and revoked_status["status"] == "failed"
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("UPDATE memberships SET status = 'active' WHERE id = :id"), {"id": ids["member_a"]}
            )

        unknown_id = uuid4()
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("""
                    INSERT INTO jobs (id, organization_id, type, schema_version, subject_type, subject_id,
                                      actor_id, actor_membership_id, idempotency_key_digest,
                                      idempotency_key_version, request_fingerprint, status, created_at, available_at)
                    VALUES (:id, :org, 'internal_probe', 2, 'organization', :org, :actor, :member,
                            repeat('a', 64), 1, repeat('b', 64), 'queued', clock_timestamp(), clock_timestamp())
                """),
                {"id": unknown_id, "org": ids["org_a"], "actor": ids["user_a"], "member": ids["member_a"]},
            )
            await connection.execute(
                text("UPDATE job_scheduler_state SET queued_count = queued_count + 1 WHERE organization_id = :org"),
                {"org": ids["org_a"]},
            )
        assert await worker_queue.claim(("internal_probe:1",)) is None
        unknown_status = await app_queue.get_status(context_a, unknown_id)
        assert unknown_status is not None and unknown_status["status"] == "queued"
        metrics = await worker_queue.metrics(("internal_probe:1",))
        assert int(str(metrics["unsupported_contracts"])) >= 1
        assert isinstance(metrics["attempts_by_code"], dict)

        async with owner.engine.begin() as connection:
            await connection.execute(
                text("UPDATE jobs SET expires_at = clock_timestamp() - interval '1 second' WHERE id = :id"),
                {"id": failed_id},
            )
        assert await worker_queue.purge_expired() >= 1
        assert await app_queue.get_status(context_a, failed_id) is None
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(text("DELETE FROM jobs WHERE organization_id IN (:org_a, :org_b)"), ids)
            await connection.execute(
                text("DELETE FROM job_scheduler_state WHERE organization_id IN (:org_a, :org_b)"), ids
            )
            await connection.execute(text("DELETE FROM memberships WHERE id IN (:member_a, :member_b)"), ids)
            await connection.execute(text("DELETE FROM organizations WHERE id IN (:org_a, :org_b)"), ids)
            await connection.execute(text("DELETE FROM users WHERE id IN (:user_a, :user_b)"), ids)
        await app.close()
        await owner.close()
        await worker.close()
