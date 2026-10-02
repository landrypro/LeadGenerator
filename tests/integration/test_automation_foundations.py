import os
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from backend.app.application.tenancy import TenantContext
from backend.app.infrastructure.postgres import PostgresDatabase

pytestmark = pytest.mark.integration

AUTOMATION_TABLES = (
    "automation_organization_settings",
    "automation_playbooks",
    "automation_playbook_versions",
    "automation_decisions",
    "automation_exceptions",
)


@dataclass(frozen=True, slots=True)
class AutomationFixture:
    organization_a_id: UUID
    organization_b_id: UUID
    actor_a_id: UUID
    actor_b_id: UUID


def database_urls() -> tuple[str, str]:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not app_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("Les URL PostgreSQL applicative et proprietaire sont requises.")
    return app_url, owner_url


def create_database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=2,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=2_000,
    )


async def create_fixture(owner: PostgresDatabase) -> AutomationFixture:
    fixture = AutomationFixture(uuid4(), uuid4(), uuid4(), uuid4())
    now = datetime.now(UTC).replace(microsecond=0)
    async with owner.engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO users (id, email, email_normalized, display_name, password_hash, status, created_at, updated_at)
                VALUES
                    (:actor_a_id, :email_a, :email_a, 'Automatisation A', 'hash-a', 'active', :now, :now),
                    (:actor_b_id, :email_b, :email_b, 'Automatisation B', 'hash-b', 'active', :now, :now)
                """
            ),
            {
                "actor_a_id": fixture.actor_a_id,
                "actor_b_id": fixture.actor_b_id,
                "email_a": f"automation-a-{fixture.actor_a_id}@example.ca",
                "email_b": f"automation-b-{fixture.actor_b_id}@example.ca",
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO organizations (id, name, timezone, status, created_by, activated_at, created_at, updated_at)
                VALUES
                    (:organization_a_id, 'Automatisation A', 'America/Toronto', 'active', :actor_a_id, :now, :now, :now),
                    (:organization_b_id, 'Automatisation B', 'America/Toronto', 'active', :actor_b_id, :now, :now, :now)
                """
            ),
            {
                "organization_a_id": fixture.organization_a_id,
                "organization_b_id": fixture.organization_b_id,
                "actor_a_id": fixture.actor_a_id,
                "actor_b_id": fixture.actor_b_id,
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO automation_organization_settings (
                    id, organization_id, automation_enabled, suspension_generation, created_at, updated_at, version
                ) VALUES
                    (:setting_a_id, :organization_a_id, false, 0, :now, :now, 1),
                    (:setting_b_id, :organization_b_id, false, 0, :now, :now, 1)
                """
            ),
            {
                "setting_a_id": uuid4(),
                "setting_b_id": uuid4(),
                "organization_a_id": fixture.organization_a_id,
                "organization_b_id": fixture.organization_b_id,
                "now": now,
            },
        )
    return fixture


async def delete_fixture(owner: PostgresDatabase, fixture: AutomationFixture) -> None:
    async with owner.engine.begin() as connection:
        await connection.execute(
            text(
                "DELETE FROM automation_organization_settings WHERE organization_id IN (:organization_a_id, :organization_b_id)"
            ),
            {"organization_a_id": fixture.organization_a_id, "organization_b_id": fixture.organization_b_id},
        )
        await connection.execute(
            text("DELETE FROM organizations WHERE id IN (:organization_a_id, :organization_b_id)"),
            {"organization_a_id": fixture.organization_a_id, "organization_b_id": fixture.organization_b_id},
        )
        await connection.execute(
            text("DELETE FROM users WHERE id IN (:actor_a_id, :actor_b_id)"),
            {"actor_a_id": fixture.actor_a_id, "actor_b_id": fixture.actor_b_id},
        )


async def test_automation_foundation_tables_are_read_only_and_rls_tenant_isolated() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_fixture(owner)
    try:
        async with owner.engine.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            """
                            SELECT relname, relrowsecurity, relforcerowsecurity
                            FROM pg_class
                            WHERE relname = ANY(:table_names)
                            """
                        ),
                        {"table_names": list(AUTOMATION_TABLES)},
                    )
                )
                .mappings()
                .all()
            )
            policies = set(
                (
                    await connection.scalars(
                        text(
                            """
                            SELECT policyname
                            FROM pg_policies
                            WHERE schemaname = 'public' AND tablename = ANY(:table_names)
                            """
                        ),
                        {"table_names": list(AUTOMATION_TABLES)},
                    )
                ).all()
            )
            public_grants = await connection.scalar(
                text(
                    """
                    SELECT count(*) FROM information_schema.table_privileges
                    WHERE table_schema = 'public' AND table_name = ANY(:table_names) AND grantee = 'PUBLIC'
                    """
                ),
                {"table_names": list(AUTOMATION_TABLES)},
            )

        async with app.unit_of_work() as unit_of_work:
            without_context = await unit_of_work.session.scalar(
                text("SELECT count(*) FROM automation_organization_settings")
            )
            privileges = (
                (
                    await unit_of_work.session.execute(
                        text(
                            """
                            SELECT
                                has_table_privilege(current_user, 'public.automation_playbooks', 'INSERT') AS can_insert,
                                has_table_privilege(current_user, 'public.automation_decisions', 'UPDATE') AS can_update,
                                has_table_privilege(current_user, 'public.automation_exceptions', 'DELETE') AS can_delete
                            """
                        )
                    )
                )
                .mappings()
                .one()
            )

        async with app.tenant_unit_of_work(
            TenantContext(fixture.actor_a_id, fixture.organization_a_id, f"automation-foundation-a-{uuid4()}")
        ) as unit_of_work:
            visible_to_a = await unit_of_work.session.scalar(
                text("SELECT count(*) FROM automation_organization_settings")
            )

        async with app.tenant_unit_of_work(
            TenantContext(fixture.actor_b_id, fixture.organization_b_id, f"automation-foundation-b-{uuid4()}")
        ) as unit_of_work:
            visible_to_b = await unit_of_work.session.scalar(
                text(
                    "SELECT count(*) FROM automation_organization_settings WHERE organization_id = :organization_a_id"
                ),
                {"organization_a_id": fixture.organization_a_id},
            )
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert {row["relname"] for row in rows} == set(AUTOMATION_TABLES)
    assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rows)
    assert policies == {f"{table_name}_tenant_read" for table_name in AUTOMATION_TABLES}
    assert public_grants == 0
    assert without_context == 0
    assert visible_to_a == 1
    assert visible_to_b == 0
    assert not any(privileges.values())
