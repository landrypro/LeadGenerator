"""Real PostgreSQL and worker-role contract for one private CSV export."""

from __future__ import annotations

import csv
import io
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from backend.app.application.tenancy import TenantContext
from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.export_service import ExportNotFound, ExportService
from backend.app.infrastructure.postgres.job_queue import PostgresJobQueue, _set_tenant

pytestmark = pytest.mark.integration


def _database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url, connect_timeout_seconds=2, pool_size=2, max_overflow=0, pool_timeout_seconds=3, statement_timeout_ms=30_000
    )


@pytest.mark.asyncio
async def test_export_is_private_tenant_scoped_and_generated_by_worker(tmp_path: Path) -> None:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    worker_url = os.environ.get("TEST_WORKER_DATABASE_URL", "")
    if not all((app_url, owner_url, worker_url)):
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("Les trois URL PostgreSQL de test sont obligatoires.")
        pytest.skip("PostgreSQL de test et rôle worker requis.")
    app, owner, worker = _database(app_url), _database(owner_url), _database(worker_url)
    secret = b"export-test-hmac-key-with-at-least-32-bytes"
    api = ExportService(app.session_factory, str(tmp_path), secret)
    processor = ExportService(worker.session_factory, str(tmp_path), secret)
    queue = PostgresJobQueue(worker.session_factory)
    ids = {name: uuid4() for name in ("org_a", "org_b", "user_a", "user_b", "member_a", "member_b", "prospect")}
    now = datetime.now(UTC)
    context_a = TenantContext(actor_id=ids["user_a"], organization_id=ids["org_a"], request_id="export-a")
    context_b = TenantContext(actor_id=ids["user_b"], organization_id=ids["org_b"], request_id="export-b")
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("""
                INSERT INTO users (id, email, email_normalized, display_name, password_hash, status,
                                   created_at, updated_at) VALUES
                  (:user_a, :email_a, :email_a, 'Export A', 'hash', 'active', :now, :now),
                  (:user_b, :email_b, :email_b, 'Export B', 'hash', 'active', :now, :now)
            """),
                {
                    **ids,
                    "email_a": f"export-a-{ids['user_a']}@example.ca",
                    "email_b": f"export-b-{ids['user_b']}@example.ca",
                    "now": now,
                },
            )
            await connection.execute(
                text("""
                INSERT INTO organizations (id, name, timezone, status, created_by, activated_at,
                                           created_at, updated_at) VALUES
                  (:org_a, 'Export A', 'America/Toronto', 'active', :user_a, :now, :now, :now),
                  (:org_b, 'Export B', 'America/Toronto', 'active', :user_b, :now, :now, :now)
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
            await connection.execute(
                text("""
                INSERT INTO prospects (id, organization_id, internal_alias, origin, source_label, owner_id,
                                       created_at, updated_at)
                VALUES (:prospect, :org_a, '=sensitive alias', 'manual', 'Manual', :member_a, :now, :now)
            """),
                {**ids, "now": now},
            )
        created = await api.create(
            context=context_a,
            membership_id=ids["member_a"],
            timezone_name="America/Toronto",
            dataset_code="prospects",
            scope="self",
            filters={},
            columns=None,
            idempotency_key="export-one",
        )
        again = await api.create(
            context=context_a,
            membership_id=ids["member_a"],
            timezone_name="America/Toronto",
            dataset_code="prospects",
            scope="self",
            filters={},
            columns=None,
            idempotency_key="export-one",
        )
        assert created["id"] == again["id"]
        with pytest.raises(ExportNotFound):
            await api.get(context_b, ids["member_b"], created["id"])
        async with worker.session_factory.begin() as session:
            assert (await session.execute(text("SELECT count(*) FROM export_requests"))).scalar_one() == 0
        claim = await queue.claim(("export_csv:1",))
        assert claim is not None and claim.subject_id == created["id"]
        assert await processor.generate(claim, context_a, queue) == "ok"
        assert await queue.complete(claim, context_a)
        path, dataset, _ = await api.download(context_a, ids["member_a"], created["id"])
        assert dataset == "prospects"
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")
        rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
        assert len(rows) == 1 and rows[0]["internal_alias"] == "'=sensitive alias"
        async with worker.session_factory.begin() as session:
            await _set_tenant(session, context_b)
            assert (await session.execute(text("SELECT count(*) FROM export_requests"))).scalar_one() == 0
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(text("DELETE FROM audit_events WHERE organization_id IN (:org_a, :org_b)"), ids)
            await connection.execute(
                text("DELETE FROM export_artifacts WHERE organization_id IN (:org_a, :org_b)"), ids
            )
            await connection.execute(text("DELETE FROM export_requests WHERE organization_id IN (:org_a, :org_b)"), ids)
            await connection.execute(text("DELETE FROM jobs WHERE organization_id IN (:org_a, :org_b)"), ids)
            await connection.execute(
                text("DELETE FROM job_scheduler_state WHERE organization_id IN (:org_a, :org_b)"), ids
            )
            await connection.execute(text("DELETE FROM prospects WHERE id = :prospect"), ids)
            await connection.execute(text("DELETE FROM memberships WHERE id IN (:member_a, :member_b)"), ids)
            await connection.execute(text("DELETE FROM organizations WHERE id IN (:org_a, :org_b)"), ids)
            await connection.execute(text("DELETE FROM users WHERE id IN (:user_a, :user_b)"), ids)
        await app.close()
        await worker.close()
        await owner.close()
