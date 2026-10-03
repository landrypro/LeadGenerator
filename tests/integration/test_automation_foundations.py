import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from backend.app.application.tenancy import TenantContext
from backend.app.cli.worker import Worker, WorkerConfig
from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.automation_runtime import AutomationRuntime
from backend.app.infrastructure.postgres.job_queue import PostgresJobQueue

pytestmark = pytest.mark.integration

AUTOMATION_TABLES = (
    "automation_organization_settings",
    "automation_playbooks",
    "automation_playbook_versions",
    "automation_preflights",
    "automation_decisions",
    "automation_admissions",
    "automation_exceptions",
)


@dataclass(frozen=True, slots=True)
class AutomationFixture:
    organization_a_id: UUID
    organization_b_id: UUID
    actor_a_id: UUID
    actor_b_id: UUID
    membership_a_id: UUID
    membership_b_id: UUID
    prospect_a_id: UUID
    prospect_b_id: UUID


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


def worker_database_url() -> str:
    worker_url = os.environ.get("TEST_WORKER_DATABASE_URL", "")
    if not worker_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_WORKER_DATABASE_URL est obligatoire.")
        pytest.skip("L'URL PostgreSQL du worker est requise.")
    return worker_url


async def create_fixture(owner: PostgresDatabase) -> AutomationFixture:
    fixture = AutomationFixture(uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4())
    now = datetime.now(UTC).replace(microsecond=0)
    expires_at = now + timedelta(hours=1)
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
                INSERT INTO memberships (
                    id, organization_id, user_id, role, status, created_by, updated_by, created_at, updated_at, version
                ) VALUES
                    (:membership_a_id, :organization_a_id, :actor_a_id, 'manager', 'active', :actor_a_id, :actor_a_id, :now, :now, 1),
                    (:membership_b_id, :organization_b_id, :actor_b_id, 'manager', 'active', :actor_b_id, :actor_b_id, :now, :now, 1)
                """
            ),
            {
                "membership_a_id": fixture.membership_a_id,
                "membership_b_id": fixture.membership_b_id,
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
                INSERT INTO prospects (
                    id, organization_id, internal_alias, origin, source_label, owner_id, created_at, updated_at
                ) VALUES
                    (:prospect_a_id, :organization_a_id, 'Prospect Automatisation A', 'manual', 'Test', :membership_a_id, :now, :now),
                    (:prospect_b_id, :organization_b_id, 'Prospect Automatisation B', 'manual', 'Test', :membership_b_id, :now, :now)
                """
            ),
            {
                "prospect_a_id": fixture.prospect_a_id,
                "prospect_b_id": fixture.prospect_b_id,
                "organization_a_id": fixture.organization_a_id,
                "organization_b_id": fixture.organization_b_id,
                "membership_a_id": fixture.membership_a_id,
                "membership_b_id": fixture.membership_b_id,
                "now": now,
            },
        )
        playbook_a_id = uuid4()
        playbook_b_id = uuid4()
        version_a_id = uuid4()
        version_b_id = uuid4()
        preflight_a_id = uuid4()
        preflight_b_id = uuid4()
        decision_a_id = uuid4()
        decision_b_id = uuid4()
        await connection.execute(
            text(
                """
                INSERT INTO automation_playbooks (
                    id, organization_id, code, state, prepare_enabled, suspension_generation, created_at, updated_at, version
                ) VALUES
                    (:playbook_a_id, :organization_a_id, 'new_prospect', 'preflight_required', false, 0, :now, :now, 1),
                    (:playbook_b_id, :organization_b_id, 'new_prospect', 'preflight_required', false, 0, :now, :now, 1)
                """
            ),
            {
                "playbook_a_id": playbook_a_id,
                "playbook_b_id": playbook_b_id,
                "organization_a_id": fixture.organization_a_id,
                "organization_b_id": fixture.organization_b_id,
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO automation_playbook_versions (
                    id, organization_id, playbook_id, version_number, ruleset_version, configuration,
                    snapshot_fingerprint, created_by_membership_id, created_at
                ) VALUES
                    (:version_a_id, :organization_a_id, :playbook_a_id, 1, 'FEU-1.0', '{}'::jsonb,
                     :fingerprint_a, :membership_a_id, :now),
                    (:version_b_id, :organization_b_id, :playbook_b_id, 1, 'FEU-1.0', '{}'::jsonb,
                     :fingerprint_b, :membership_b_id, :now)
                """
            ),
            {
                "version_a_id": version_a_id,
                "version_b_id": version_b_id,
                "organization_a_id": fixture.organization_a_id,
                "organization_b_id": fixture.organization_b_id,
                "playbook_a_id": playbook_a_id,
                "playbook_b_id": playbook_b_id,
                "fingerprint_a": "a" * 64,
                "fingerprint_b": "b" * 64,
                "membership_a_id": fixture.membership_a_id,
                "membership_b_id": fixture.membership_b_id,
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO automation_preflights (
                    id, organization_id, playbook_version_id, requested_by_membership_id, ruleset_version,
                    scope_fingerprint, state, correlation_id, subject_count, green_count, yellow_count, red_count,
                    to_verify_count, created_at, updated_at, expires_at
                ) VALUES
                    (:preflight_a_id, :organization_a_id, :version_a_id, :membership_a_id, 'FEU-1.0',
                     :scope_a, 'completed', :correlation_a, 1, 1, 0, 0, 0, :now, :now, :expires_at),
                    (:preflight_b_id, :organization_b_id, :version_b_id, :membership_b_id, 'FEU-1.0',
                     :scope_b, 'completed', :correlation_b, 1, 1, 0, 0, 0, :now, :now, :expires_at)
                """
            ),
            {
                "preflight_a_id": preflight_a_id,
                "preflight_b_id": preflight_b_id,
                "organization_a_id": fixture.organization_a_id,
                "organization_b_id": fixture.organization_b_id,
                "version_a_id": version_a_id,
                "version_b_id": version_b_id,
                "membership_a_id": fixture.membership_a_id,
                "membership_b_id": fixture.membership_b_id,
                "scope_a": "c" * 64,
                "scope_b": "d" * 64,
                "correlation_a": uuid4(),
                "correlation_b": uuid4(),
                "now": now,
                "expires_at": expires_at,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO automation_decisions (
                    id, organization_id, preflight_id, playbook_version_id, subject_type, subject_id, fire_level,
                    next_action, reason_codes, context_fingerprint, correlation_id, outcome, created_at, expires_at
                ) VALUES
                    (:decision_a_id, :organization_a_id, :preflight_a_id, :version_a_id, 'prospect', :prospect_a_id,
                     'green', 'prepare', '["ready"]'::jsonb, :context_a, :decision_correlation_a, 'prepared', :now, :expires_at),
                    (:decision_b_id, :organization_b_id, :preflight_b_id, :version_b_id, 'prospect', :prospect_b_id,
                     'green', 'prepare', '["ready"]'::jsonb, :context_b, :decision_correlation_b, 'prepared', :now, :expires_at)
                """
            ),
            {
                "decision_a_id": decision_a_id,
                "decision_b_id": decision_b_id,
                "organization_a_id": fixture.organization_a_id,
                "organization_b_id": fixture.organization_b_id,
                "preflight_a_id": preflight_a_id,
                "preflight_b_id": preflight_b_id,
                "version_a_id": version_a_id,
                "version_b_id": version_b_id,
                "prospect_a_id": fixture.prospect_a_id,
                "prospect_b_id": fixture.prospect_b_id,
                "context_a": "e" * 64,
                "context_b": "f" * 64,
                "decision_correlation_a": uuid4(),
                "decision_correlation_b": uuid4(),
                "now": now,
                "expires_at": expires_at,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO automation_admissions (
                    id, organization_id, prospect_id, playbook_version_id, requested_by_membership_id, preflight_id,
                    decision_id, functional_identity_fingerprint, idempotency_key_digest, request_fingerprint,
                    correlation_id, state, created_at, updated_at
                ) VALUES
                    (:admission_a_id, :organization_a_id, :prospect_a_id, :version_a_id, :membership_a_id, :preflight_a_id,
                     :decision_a_id, :functional_a, :idempotency_a, :request_a, :correlation_a, 'ready_to_prepare', :now, :now),
                    (:admission_b_id, :organization_b_id, :prospect_b_id, :version_b_id, :membership_b_id, :preflight_b_id,
                     :decision_b_id, :functional_b, :idempotency_b, :request_b, :correlation_b, 'ready_to_prepare', :now, :now)
                """
            ),
            {
                "admission_a_id": uuid4(),
                "admission_b_id": uuid4(),
                "organization_a_id": fixture.organization_a_id,
                "organization_b_id": fixture.organization_b_id,
                "prospect_a_id": fixture.prospect_a_id,
                "prospect_b_id": fixture.prospect_b_id,
                "version_a_id": version_a_id,
                "version_b_id": version_b_id,
                "membership_a_id": fixture.membership_a_id,
                "membership_b_id": fixture.membership_b_id,
                "preflight_a_id": preflight_a_id,
                "preflight_b_id": preflight_b_id,
                "decision_a_id": decision_a_id,
                "decision_b_id": decision_b_id,
                "functional_a": "1" * 64,
                "functional_b": "2" * 64,
                "idempotency_a": "3" * 64,
                "idempotency_b": "4" * 64,
                "request_a": "5" * 64,
                "request_b": "6" * 64,
                "correlation_a": uuid4(),
                "correlation_b": uuid4(),
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
    organizations = {"organization_a_id": fixture.organization_a_id, "organization_b_id": fixture.organization_b_id}
    async with owner.engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM prospect_task_events WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            organizations,
        )
        await connection.execute(
            text("DELETE FROM automation_admissions WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            organizations,
        )
        await connection.execute(
            text("DELETE FROM prospect_tasks WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            organizations,
        )
        await connection.execute(
            text("DELETE FROM automation_exceptions WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            organizations,
        )
        await connection.execute(
            text("DELETE FROM automation_decisions WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            organizations,
        )
        await connection.execute(
            text("DELETE FROM automation_preflights WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            organizations,
        )
        await connection.execute(
            text(
                "DELETE FROM automation_playbook_versions WHERE organization_id IN (:organization_a_id, :organization_b_id)"
            ),
            organizations,
        )
        await connection.execute(
            text("DELETE FROM automation_playbooks WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            organizations,
        )
        await connection.execute(
            text(
                "DELETE FROM automation_organization_settings WHERE organization_id IN (:organization_a_id, :organization_b_id)"
            ),
            organizations,
        )
        await connection.execute(
            text("DELETE FROM audit_events WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            organizations,
        )
        await connection.execute(
            text("DELETE FROM jobs WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            organizations,
        )
        await connection.execute(
            text("DELETE FROM job_scheduler_state WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            organizations,
        )
        await connection.execute(
            text("DELETE FROM prospects WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            organizations,
        )
        await connection.execute(
            text("DELETE FROM memberships WHERE id IN (:membership_a_id, :membership_b_id)"),
            {"membership_a_id": fixture.membership_a_id, "membership_b_id": fixture.membership_b_id},
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
            parent_child_count = await connection.scalar(
                text(
                    """
                        SELECT count(*)
                        FROM automation_preflights AS preflight
                        JOIN automation_decisions AS decision
                          ON decision.organization_id = preflight.organization_id
                         AND decision.preflight_id = preflight.id
                        WHERE preflight.organization_id IN (:organization_a_id, :organization_b_id)
                        """
                ),
                {
                    "organization_a_id": fixture.organization_a_id,
                    "organization_b_id": fixture.organization_b_id,
                },
            )

        async with app.unit_of_work() as unit_of_work:
            without_context = await unit_of_work.session.scalar(
                text("SELECT count(*) FROM automation_organization_settings")
            )
            preflights_without_context = await unit_of_work.session.scalar(
                text("SELECT count(*) FROM automation_preflights")
            )
            admissions_without_context = await unit_of_work.session.scalar(
                text("SELECT count(*) FROM automation_admissions")
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
            preflights_visible_to_a = await unit_of_work.session.scalar(
                text("SELECT count(*) FROM automation_preflights")
            )
            admissions_visible_to_a = await unit_of_work.session.scalar(
                text("SELECT count(*) FROM automation_admissions")
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
            decisions_visible_to_b = await unit_of_work.session.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM automation_decisions
                    WHERE organization_id = :organization_a_id
                    """
                ),
                {"organization_a_id": fixture.organization_a_id},
            )
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert {row["relname"] for row in rows} == set(AUTOMATION_TABLES)
    assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rows)
    assert policies == {
        *(f"{table_name}_tenant_read" for table_name in AUTOMATION_TABLES),
        "automation_admissions_worker_runtime",
    }
    assert public_grants == 0
    assert parent_child_count == 2
    assert without_context == 0
    assert preflights_without_context == 0
    assert admissions_without_context == 0
    assert visible_to_a == 1
    assert preflights_visible_to_a == 1
    assert admissions_visible_to_a == 1
    assert visible_to_b == 0
    assert decisions_visible_to_b == 0
    assert not any(privileges.values())


async def test_manual_automation_admission_is_idempotent_and_worker_prepares_one_task() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    worker = create_database(worker_database_url())
    fixture = await create_fixture(owner)
    context = TenantContext(
        actor_id=fixture.actor_a_id,
        organization_id=fixture.organization_a_id,
        request_id=f"automation-admission-{uuid4()}",
    )
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE automation_organization_settings
                    SET automation_enabled = true
                    WHERE organization_id = :organization_id
                    """
                ),
                {"organization_id": fixture.organization_a_id},
            )
            await connection.execute(
                text(
                    """
                    UPDATE automation_playbooks
                    SET state = 'active_prepare', prepare_enabled = true
                    WHERE organization_id = :organization_id AND code = 'new_prospect'
                    """
                ),
                {"organization_id": fixture.organization_a_id},
            )

        app_runtime = AutomationRuntime(
            app.session_factory,
            global_enabled=True,
            idempotency_secret=b"automation-runtime-integration-secret",
        )
        first = await app_runtime.admit_manual(
            context=context,
            internal_alias="Prospect admission IMP-A4",
            requested_membership_id=fixture.membership_a_id,
            assigned_membership_id=fixture.membership_a_id,
            idempotency_key="automation-integration-key",
        )
        replay = await app_runtime.admit_manual(
            context=context,
            internal_alias="Prospect admission IMP-A4",
            requested_membership_id=fixture.membership_a_id,
            assigned_membership_id=fixture.membership_a_id,
            idempotency_key="automation-integration-key",
        )
        assert first.replayed is False
        assert replay.replayed is True
        assert replay.prospect.id == first.prospect.id
        assert replay.job_id == first.job_id

        queue = PostgresJobQueue(worker.session_factory)
        worker_process = Worker(
            queue,
            worker,
            WorkerConfig(
                database_url="postgresql+asyncpg://prospect_worker:unused@localhost/prospect",
                import_temp_directory=".",
                idempotency_secret=b"automation-runtime-integration-secret",
                automation_enabled=True,
            ),
        )
        assert await worker_process.run_once() is True

        async with owner.engine.connect() as connection:
            admission = (
                (
                    await connection.execute(
                        text(
                            """
                            SELECT state, result_code, task_id, job_id
                        FROM automation_admissions
                        WHERE id = :admission_id
                        """
                        ),
                        {"admission_id": first.admission_id},
                    )
                )
                .mappings()
                .one()
            )
            task = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT assigned_membership_id, title, priority, status, due_at
                        FROM prospect_tasks
                        WHERE id = :task_id
                        """
                        ),
                        {"task_id": admission["task_id"]},
                    )
                )
                .mappings()
                .one()
            )
            job = (
                (
                    await connection.execute(
                        text("SELECT status, result_code FROM jobs WHERE id = :job_id"),
                        {"job_id": admission["job_id"]},
                    )
                )
                .mappings()
                .one()
            )
            privileges = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT
                          has_function_privilege('prospect_app',
                            'app_private.prepare_automation_new_prospect_task(uuid,uuid,boolean,text)', 'EXECUTE')
                            AS app_can_prepare,
                          has_function_privilege('prospect_worker',
                            'app_private.admit_manual_new_prospect_automation(text,uuid,uuid,text,text,text,uuid,boolean,text)', 'EXECUTE')
                            AS worker_can_admit
                        """
                        )
                    )
                )
                .mappings()
                .one()
            )
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()
        await worker.close()

    assert admission["state"] == "prepared"
    assert admission["result_code"] == "prepared"
    assert job == {"status": "succeeded", "result_code": "prepared"}
    assert task["assigned_membership_id"] == fixture.membership_a_id
    assert task["title"] == "Prendre en charge le prospect Prospect admission IMP-A4"
    assert task["priority"] == "normal"
    assert task["status"] == "open"
    assert task["due_at"] is not None
    assert privileges["app_can_prepare"] is False
    assert privileges["worker_can_admit"] is False
