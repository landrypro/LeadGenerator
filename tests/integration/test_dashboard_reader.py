from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.dashboard import GetDashboardSummaryUseCase
from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.dashboard_reader import PostgresDashboardReader

pytestmark = pytest.mark.integration
NOW = datetime(2026, 9, 23, 16, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


def database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url, connect_timeout_seconds=2, pool_size=1, max_overflow=0, pool_timeout_seconds=2, statement_timeout_ms=5_000
    )


@pytest.mark.asyncio
async def test_dashboard_reader_uses_rls_and_corrected_activity_chain() -> None:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not app_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("Les URL PostgreSQL de test sont requises.")
    app, owner = database(app_url), database(owner_url)
    ids = {
        name: uuid4()
        for name in (
            "org_a",
            "org_b",
            "user_a",
            "user_b",
            "member_a",
            "member_b",
            "prospect_a",
            "prospect_b",
            "task_a",
            "activity_a",
            "correction_a",
            "transition_a",
            "opportunity_a",
        )
    }
    ids.update(email_a=f"dashboard-a-{ids['user_a']}@example.ca", email_b=f"dashboard-b-{ids['user_b']}@example.ca")
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("""
                INSERT INTO users (id, email, email_normalized, display_name, password_hash, status,
                                   created_at, updated_at) VALUES
                  (:user_a, :email_a, :email_a, 'Dashboard A', 'hash', 'active', :now, :now),
                  (:user_b, :email_b, :email_b, 'Dashboard B', 'hash', 'active', :now, :now)
            """),
                {**ids, "now": NOW},
            )
            await connection.execute(
                text("""
                INSERT INTO organizations (id, name, timezone, status, created_by, activated_at,
                                           created_at, updated_at) VALUES
                  (:org_a, 'Dashboard A', 'America/Toronto', 'active', :user_a, :now, :now, :now),
                  (:org_b, 'Dashboard B', 'America/Toronto', 'active', :user_b, :now, :now, :now)
            """),
                {**ids, "now": NOW},
            )
            await connection.execute(
                text("""
                INSERT INTO memberships (id, organization_id, user_id, role, created_by, updated_by,
                                         created_at, updated_at, version) VALUES
                  (:member_a, :org_a, :user_a, 'admin', :user_a, :user_a, :now, :now, 1),
                  (:member_b, :org_b, :user_b, 'admin', :user_b, :user_b, :now, :now, 1)
            """),
                {**ids, "now": NOW},
            )
            await connection.execute(
                text("""
                INSERT INTO prospects (id, organization_id, internal_alias, origin, source_label, owner_id,
                                       stage_code, version, created_at, updated_at) VALUES
                  (:prospect_a, :org_a, 'Prospect A', 'manual', 'Dashboard', :member_a,
                   'qualifying', 2, '2026-09-23T14:00:00Z', :now),
                  (:prospect_b, :org_b, 'Prospect B', 'manual', 'Dashboard', :member_b,
                   'new', 1, '2026-09-23T14:00:00Z', :now)
            """),
                {**ids, "now": NOW},
            )
            await connection.execute(
                text("""
                INSERT INTO prospect_stage_transitions
                  (id, organization_id, prospect_id, actor_id, from_stage, to_stage, from_version,
                   resulting_version, idempotency_key, command_fingerprint, occurred_at)
                VALUES (:transition_a, :org_a, :prospect_a, :user_a, 'new', 'qualifying', 1, 2,
                        'dashboard-test', 'dashboard-test', '2026-09-23T14:30:00Z')
            """),
                ids,
            )
            await connection.execute(
                text("""
                INSERT INTO prospect_tasks
                  (id, organization_id, prospect_id, created_by, assigned_membership_id, title, status,
                   due_at, created_at, updated_at) VALUES
                  (:task_a, :org_a, :prospect_a, :user_a, :member_a, 'Relancer', 'open',
                   '2026-09-23T18:00:00Z', :now, :now)
            """),
                {**ids, "now": NOW},
            )
            await connection.execute(
                text("""
                INSERT INTO prospect_activities
                  (id, organization_id, prospect_id, actor_id, activity_type, direction, summary,
                   occurred_at, created_at) VALUES
                  (:activity_a, :org_a, :prospect_a, :user_a, 'call', 'outbound', 'Appel',
                   '2026-09-23T14:45:00Z', '2026-09-23T14:46:00Z')
            """),
                ids,
            )
            await connection.execute(
                text("""
                INSERT INTO prospect_activities
                  (id, organization_id, prospect_id, actor_id, activity_type, direction, summary,
                   occurred_at, created_at, correction_of_activity_id, correction_reason) VALUES
                  (:correction_a, :org_a, :prospect_a, :user_a, 'meeting', 'outbound', 'Rendez-vous',
                   '2026-09-23T15:00:00Z', '2026-09-23T15:01:00Z', :activity_a, 'Correction')
            """),
                ids,
            )
            await connection.execute(
                text("""
                INSERT INTO opportunities
                  (id, organization_id, prospect_id, owner_membership_id, name, amount, currency_code,
                   probability, stage_code, expected_close_on, created_by, created_at, updated_at) VALUES
                  (:opportunity_a, :org_a, :prospect_a, :member_a, 'Affaire', 1000.0000, 'CAD',
                   50, 'discovery', '2026-10-01', :user_a, :now, :now)
            """),
                {**ids, "now": NOW},
            )

        reader = PostgresDashboardReader(app.session_factory)
        context = TenantContext(ids["user_a"], ids["org_a"], "dashboard-integration")
        assert await reader.owner_user_id(context, ids["member_b"]) is None
        result = await GetDashboardSummaryUseCase(reader, FixedClock()).execute(
            context=context,
            membership_id=ids["member_a"],
            timezone="America/Toronto",
            scope="organization",
            owner_membership_id=None,
            period="day",
            start_on=None,
            end_on=None,
            can_read_self=True,
            can_read_organization=True,
        )
        assert result["prospects_by_stage"][1]["count"] == 1
        assert result["prospects_by_stage"][0]["count"] == 0
        assert result["tasks"] == {"due_today": 1, "overdue": 0}
        assert result["activities_by_type"][0]["count"] == 0
        assert result["activities_by_type"][1]["count"] == 1
        assert result["stage_passage"][0]["cohort"] == 1
        assert result["stage_passage"][0]["advanced"] == 1
        assert result["pipeline_by_currency"] == [
            {"currency_code": "CAD", "amount": "1000.0000", "weighted_amount": "500.0000"}
        ]
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(text("DELETE FROM audit_events WHERE organization_id IN (:org_a, :org_b)"), ids)
            await connection.execute(text("DELETE FROM organizations WHERE id IN (:org_a, :org_b)"), ids)
            await connection.execute(text("DELETE FROM users WHERE id IN (:user_a, :user_b)"), ids)
        await app.close()
        await owner.close()
