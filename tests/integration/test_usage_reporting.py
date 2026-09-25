from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.app.application.ports.usage import UsageEvent
from backend.app.application.tenancy import TenantContext
from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.job_queue import PostgresJobQueue
from backend.app.infrastructure.postgres.usage_store import PostgresUsageStore

pytestmark = pytest.mark.integration


def database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=2,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=10_000,
    )


@pytest.mark.asyncio
async def test_usage_registry_is_idempotent_aggregated_and_tenant_scoped() -> None:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    worker_url = os.environ.get("TEST_WORKER_DATABASE_URL", "")
    if not app_url or not owner_url or not worker_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("Les URL PostgreSQL application, migration et worker sont obligatoires.")
        pytest.skip("Les URL PostgreSQL de test sont requises.")
    app, owner, worker = database(app_url), database(owner_url), database(worker_url)
    ids = {name: uuid4() for name in ("org_a", "org_b", "user_a", "user_b", "member_a", "member_b", "operation")}
    now = datetime(2026, 9, 24, 15, tzinfo=UTC)
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("""
                    INSERT INTO users (id, email, email_normalized, display_name, password_hash, status,
                                       created_at, updated_at) VALUES
                    (:user_a, :email_a, :email_a, 'Usage A', 'hash', 'active', :now, :now),
                    (:user_b, :email_b, :email_b, 'Usage B', 'hash', 'active', :now, :now)
                """),
                {
                    **ids,
                    "email_a": f"usage-a-{ids['user_a']}@example.ca",
                    "email_b": f"usage-b-{ids['user_b']}@example.ca",
                    "now": now,
                },
            )
            await connection.execute(
                text("""
                    INSERT INTO organizations (id, name, timezone, status, created_by, activated_at,
                                               created_at, updated_at) VALUES
                    (:org_a, 'Usage A', 'UTC', 'active', :user_a, :now, :now, :now),
                    (:org_b, 'Usage B', 'UTC', 'active', :user_b, :now, :now, :now)
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

        store = PostgresUsageStore(app.session_factory)
        context = TenantContext(ids["user_a"], ids["org_a"], "usage-integration")
        event = UsageEvent(
            context=context,
            membership_id=ids["member_a"],
            operation_id=ids["operation"],
            usage_code="google.places_text_search.quota",
            event_kind="quota_reserved",
            outcome="accepted",
            occurred_at=now,
            policy_code="server_default_v1",
            user_limit=20,
            organization_limit=100,
            warning_threshold_percent=80,
        )
        await store.record(event)
        await store.record(event)

        personal = await store.report(context, start_on=now.date(), end_on=now.date(), user_id=ids["user_a"])
        organization = await store.report(context, start_on=now.date(), end_on=now.date(), user_id=None)
        assert personal["rows"][0]["unit_count"] == 1
        assert organization["rows"][0]["unit_count"] == 1

        attempted_at = datetime.now(UTC) - timedelta(minutes=31)
        await store.record(
            UsageEvent(
                context=context,
                membership_id=ids["member_a"],
                operation_id=uuid4(),
                usage_code="google.places_details.request",
                event_kind="upstream_attempted",
                outcome="attempted",
                occurred_at=attempted_at,
            )
        )
        assert await PostgresJobQueue(worker.session_factory).reconcile_usage() == 1
        reconciled = await store.report(
            context, start_on=attempted_at.date(), end_on=attempted_at.date(), user_id=ids["user_a"]
        )
        assert any(row["outcome"] == "indeterminate" for row in reconciled["rows"])

        old_operation, expired_operation = uuid4(), uuid4()
        for operation_id, age in ((old_operation, 91), (expired_operation, 401)):
            await store.record(
                UsageEvent(
                    context=context,
                    membership_id=ids["member_a"],
                    operation_id=operation_id,
                    usage_code="google.places_autocomplete.request",
                    event_kind="upstream_succeeded",
                    outcome="succeeded",
                    occurred_at=datetime.now(UTC) - timedelta(days=age),
                )
            )
        purged = await PostgresJobQueue(worker.session_factory).purge_usage(batch_size=1000)
        assert purged["events"] >= 2
        assert purged["counters"] >= 2
        async with owner.engine.begin() as connection:
            assert (
                await connection.execute(
                    text("SELECT count(*) FROM usage_operation_events WHERE operation_id = ANY(:operations)"),
                    {"operations": [old_operation, expired_operation]},
                )
            ).scalar_one() == 0

        async with app.session_factory() as session:
            await session.execute(
                text("SELECT set_config('app.actor_id', :actor, true)"), {"actor": str(ids["user_a"])}
            )
            await session.execute(
                text("SELECT set_config('app.organization_id', :org, true)"), {"org": str(ids["org_a"])}
            )
            with pytest.raises(DBAPIError):
                await session.execute(text("DELETE FROM usage_operation_events WHERE operation_id = :operation"), ids)
            await session.rollback()
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM usage_daily_counters WHERE organization_id IN (:org_a, :org_b)"), ids
            )
            await connection.execute(
                text("DELETE FROM usage_operation_events WHERE organization_id IN (:org_a, :org_b)"), ids
            )
            await connection.execute(text("DELETE FROM audit_events WHERE organization_id IN (:org_a, :org_b)"), ids)
            await connection.execute(text("DELETE FROM organizations WHERE id IN (:org_a, :org_b)"), ids)
            await connection.execute(text("DELETE FROM users WHERE id IN (:user_a, :user_b)"), ids)
        await app.close()
        await owner.close()
        await worker.close()
