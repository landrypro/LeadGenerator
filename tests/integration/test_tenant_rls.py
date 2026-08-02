import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.app.application.tenancy import TenantContext
from backend.app.infrastructure.postgres import PostgresDatabase

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class TenantFixture:
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
        pytest.skip("Les URL PostgreSQL applicative et propriétaire sont requises.")
    return app_url, owner_url


def create_database(url: str, *, pool_size: int = 1) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=2,
        pool_size=pool_size,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=2_000,
    )


async def create_tenant_fixture(owner: PostgresDatabase) -> TenantFixture:
    fixture = TenantFixture(
        organization_a_id=uuid4(),
        organization_b_id=uuid4(),
        actor_a_id=uuid4(),
        actor_b_id=uuid4(),
    )
    fixture_parameters = asdict(fixture)
    now = datetime.now(UTC).replace(microsecond=0)
    async with owner.engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, email_normalized, display_name, password_hash, status,
                    last_active_organization_id, created_at, updated_at
                )
                VALUES
                    (
                        :actor_a_id, :email_a, :email_a, 'Acteur A', 'hash-a', 'active',
                        NULL, :now, :now
                    ),
                    (
                        :actor_b_id, :email_b, :email_b, 'Acteur B', 'hash-b', 'active',
                        NULL, :now, :now
                    )
                """
            ),
            {
                **fixture_parameters,
                "email_a": f"a-{fixture.actor_a_id}@example.ca",
                "email_b": f"b-{fixture.actor_b_id}@example.ca",
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO organizations (
                    id, name, timezone, status, created_by, activated_at, created_at, updated_at
                )
                VALUES
                    (
                        :organization_a_id, 'Organisation A', 'America/Toronto', 'active',
                        :actor_a_id, :now, :now, :now
                    ),
                    (
                        :organization_b_id, 'Organisation B', 'America/Toronto', 'active',
                        :actor_b_id, :now, :now, :now
                    )
                """
            ),
            {**fixture_parameters, "now": now},
        )
        await connection.execute(
            text(
                """
                UPDATE users
                SET last_active_organization_id = CASE
                    WHEN id = CAST(:actor_a_id AS uuid) THEN CAST(:organization_a_id AS uuid)
                    ELSE CAST(:organization_b_id AS uuid)
                END
                WHERE id IN (CAST(:actor_a_id AS uuid), CAST(:actor_b_id AS uuid))
                """
            ),
            fixture_parameters,
        )
        await connection.execute(
            text(
                """
                INSERT INTO memberships (id, organization_id, user_id, role, created_by, created_at, updated_at)
                VALUES
                    (:membership_a_id, :organization_a_id, :actor_a_id, 'admin', :actor_a_id, :now, :now),
                    (:membership_b_id, :organization_b_id, :actor_b_id, 'admin', :actor_b_id, :now, :now)
                """
            ),
            {
                **fixture_parameters,
                "membership_a_id": uuid4(),
                "membership_b_id": uuid4(),
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO user_invitations (
                    id, organization_id, email, email_normalized, role, invitation_kind, token_hash,
                    expires_at, invited_by, created_at
                )
                VALUES
                    (
                        :invitation_a_id, :organization_a_id, :invited_email_a, :invited_email_a,
                        'sales', 'member', :token_a, :expires_at, :actor_a_id, :now
                    ),
                    (
                        :invitation_b_id, :organization_b_id, :invited_email_b, :invited_email_b,
                        'sales', 'member', :token_b, :expires_at, :actor_b_id, :now
                    )
                """
            ),
            {
                **fixture_parameters,
                "invitation_a_id": uuid4(),
                "invitation_b_id": uuid4(),
                "invited_email_a": f"invite-a-{uuid4()}@example.ca",
                "invited_email_b": f"invite-b-{uuid4()}@example.ca",
                "token_a": uuid4().hex * 2,
                "token_b": uuid4().hex * 2,
                "expires_at": now + timedelta(hours=1),
                "now": now,
            },
        )
    return fixture


async def delete_tenant_fixture(owner: PostgresDatabase, fixture: TenantFixture) -> None:
    fixture_parameters = asdict(fixture)
    async with owner.engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM organizations WHERE id IN (:organization_a_id, :organization_b_id)"),
            fixture_parameters,
        )
        await connection.execute(
            text("DELETE FROM users WHERE id IN (:actor_a_id, :actor_b_id)"),
            fixture_parameters,
        )


async def test_application_role_and_rls_metadata_are_locked_down() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    try:
        async with app.engine.connect() as connection:
            role = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT
                            rolname, rolsuper, rolcreatedb, rolcreaterole,
                            rolcanlogin, rolinherit, rolbypassrls
                        FROM pg_roles
                        WHERE rolname = current_user
                        """
                        )
                    )
                )
                .mappings()
                .one()
            )
            table_owners = set(
                (
                    await connection.scalars(
                        text(
                            """
                            SELECT DISTINCT pg_get_userbyid(relowner)
                            FROM pg_class
                            WHERE relname IN (
                                'organizations', 'memberships', 'user_invitations',
                                'invitation_delivery_attempts'
                            )
                            """
                        )
                    )
                ).all()
            )
            privileged_memberships = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM pg_roles AS granted_role
                    WHERE granted_role.rolname <> current_user
                      AND (granted_role.rolsuper OR granted_role.rolbypassrls)
                      AND pg_has_role(current_user, granted_role.oid, 'MEMBER')
                    """
                )
            )
            may_delete = await connection.scalar(
                text("SELECT has_table_privilege(current_user, 'public.organizations', 'DELETE')")
            )

        async with owner.engine.connect() as connection:
            rls_rows = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT relname, relrowsecurity, relforcerowsecurity
                        FROM pg_class
                        WHERE relname IN (
                            'organizations', 'memberships', 'user_invitations',
                            'invitation_delivery_attempts'
                        )
                        """
                        )
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
                            WHERE schemaname = 'public'
                              AND tablename IN (
                                  'organizations', 'memberships', 'user_invitations',
                                  'invitation_delivery_attempts'
                              )
                            """
                        )
                    )
                ).all()
            )
            function_security = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT owner_role.rolname AS owner_name, function.prosecdef, function.proconfig
                        FROM pg_proc AS function
                        JOIN pg_namespace AS namespace ON namespace.oid = function.pronamespace
                        JOIN pg_roles AS owner_role ON owner_role.oid = function.proowner
                        WHERE namespace.nspname = 'app_private'
                          AND function.proname = 'identity_memberships'
                        """
                        )
                    )
                )
                .mappings()
                .one()
            )
            public_function_grants = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM information_schema.routine_privileges
                    WHERE routine_schema = 'app_private'
                      AND routine_name = 'identity_memberships'
                      AND grantee = 'PUBLIC'
                    """
                )
            )
    finally:
        await app.close()
        await owner.close()

    assert role == {
        "rolname": "prospect_app",
        "rolsuper": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolcanlogin": True,
        "rolinherit": False,
        "rolbypassrls": False,
    }
    assert "prospect_app" not in table_owners
    assert privileged_memberships == 0
    assert may_delete is False
    assert len(rls_rows) == 4
    assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rls_rows)
    assert policies == {
        "organizations_tenant_isolation",
        "memberships_tenant_isolation",
        "user_invitations_tenant_isolation",
        "invitation_delivery_attempts_tenant_isolation",
    }
    assert function_security["owner_name"] == "prospect_rls_definer"
    assert function_security["prosecdef"] is True
    assert "search_path=pg_catalog, public, pg_temp" in function_security["proconfig"]
    assert public_function_grants == 0


async def test_rls_defaults_to_deny_and_isolates_cross_tenant_operations() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_tenant_fixture(owner)
    try:
        async with app.unit_of_work() as unit_of_work:
            no_context_count = await unit_of_work.session.scalar(text("SELECT count(*) FROM organizations"))
            await unit_of_work.session.execute(text("SELECT set_config('app.organization_id', 'not-a-uuid', true)"))
            invalid_context_count = await unit_of_work.session.scalar(text("SELECT count(*) FROM organizations"))

        context = TenantContext(
            actor_id=fixture.actor_a_id,
            organization_id=fixture.organization_a_id,
            request_id="rls-isolation",
        )
        async with app.tenant_unit_of_work(context) as unit_of_work:
            visible_organizations = set(
                (await unit_of_work.session.scalars(text("SELECT id FROM organizations"))).all()
            )
            visible_memberships = await unit_of_work.session.scalar(text("SELECT count(*) FROM memberships"))
            visible_invitations = await unit_of_work.session.scalar(text("SELECT count(*) FROM user_invitations"))
            cross_update = await unit_of_work.session.execute(
                text("UPDATE organizations SET name = 'Fuite' WHERE id = :organization_id"),
                {"organization_id": fixture.organization_b_id},
            )

        with pytest.raises(DBAPIError):
            async with app.tenant_unit_of_work(context) as unit_of_work:
                await unit_of_work.session.execute(
                    text(
                        """
                        INSERT INTO user_invitations (
                            id, organization_id, email, email_normalized, role, invitation_kind, token_hash,
                            expires_at, invited_by
                        )
                        VALUES (
                            :id, :organization_id, :email, :email, 'sales', 'member', :token_hash,
                            CURRENT_TIMESTAMP + INTERVAL '1 hour', :invited_by
                        )
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": fixture.organization_b_id,
                        "email": f"cross-{uuid4()}@example.ca",
                        "token_hash": uuid4().hex * 2,
                        "invited_by": fixture.actor_a_id,
                    },
                )

        with pytest.raises(DBAPIError):
            async with app.tenant_unit_of_work(context) as unit_of_work:
                await unit_of_work.session.execute(
                    text("DELETE FROM organizations WHERE id = :organization_id"),
                    {"organization_id": fixture.organization_b_id},
                )
    finally:
        await delete_tenant_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert no_context_count == 0
    assert invalid_context_count == 0
    assert visible_organizations == {fixture.organization_a_id}
    assert visible_memberships == 1
    assert visible_invitations == 1
    assert cross_update.rowcount == 0


async def test_tenant_context_is_cleared_after_commit_rollback_and_pool_reuse() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url, pool_size=1)
    owner = create_database(owner_url)
    fixture = await create_tenant_fixture(owner)
    context = TenantContext(
        actor_id=fixture.actor_a_id,
        organization_id=fixture.organization_a_id,
        request_id="context-lifecycle",
    )
    try:
        for should_commit in (True, False):
            async with app.tenant_unit_of_work(context) as unit_of_work:
                tenant_connection_pid = await unit_of_work.session.scalar(text("SELECT pg_backend_pid()"))
                settings = (
                    await unit_of_work.session.execute(
                        text(
                            """
                            SELECT
                                current_setting('app.actor_id', true),
                                current_setting('app.organization_id', true),
                                current_setting('app.request_id', true)
                            """
                        )
                    )
                ).one()
                if should_commit:
                    await unit_of_work.commit()
                else:
                    await unit_of_work.rollback()

            async with app.unit_of_work() as unit_of_work:
                reused_connection_pid = await unit_of_work.session.scalar(text("SELECT pg_backend_pid()"))
                context_is_empty = await unit_of_work.session.scalar(
                    text(
                        """
                        SELECT
                            NULLIF(current_setting('app.actor_id', true), '') IS NULL
                            AND NULLIF(current_setting('app.organization_id', true), '') IS NULL
                            AND NULLIF(current_setting('app.request_id', true), '') IS NULL
                        """
                    )
                )

            assert settings == (str(fixture.actor_a_id), str(fixture.organization_a_id), "context-lifecycle")
            assert reused_connection_pid == tenant_connection_pid
            assert context_is_empty is True
    finally:
        await delete_tenant_fixture(owner, fixture)
        await app.close()
        await owner.close()


async def test_identity_memberships_remain_available_through_narrow_function() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_tenant_fixture(owner)
    try:
        async with app.identity_unit_of_work() as unit_of_work:
            identity = await unit_of_work.identities.get_by_id(fixture.actor_a_id)

        async with app.unit_of_work() as unit_of_work:
            without_actor = (
                await unit_of_work.session.execute(text("SELECT * FROM app_private.identity_memberships()"))
            ).all()
    finally:
        await delete_tenant_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert identity is not None
    assert [(membership.organization_id, membership.organization_name) for membership in identity.memberships] == [
        (fixture.organization_a_id, "Organisation A")
    ]
    assert without_actor == []
