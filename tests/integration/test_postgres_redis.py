import asyncio
import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, inspect, text

from backend.app.application.errors import PlatformAdministratorAlreadyExists
from backend.app.application.use_cases import (
    BootstrapPlatformAdministratorUseCase,
    CheckReadinessUseCase,
    GetCurrentSessionUseCase,
    LoginUseCase,
    LogoutUseCase,
)
from backend.app.domain.identity import UserIdentity
from backend.app.infrastructure.clock import SystemClock
from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.models import UserModel
from backend.app.infrastructure.redis import (
    RedisInvitationRateLimiter,
    RedisLoginRateLimiter,
    RedisResource,
    RedisSessionStore,
)
from backend.app.infrastructure.security import Argon2PasswordHasher

pytestmark = pytest.mark.integration


def dependency_urls() -> tuple[str, str]:
    database_url = os.environ.get("TEST_DATABASE_URL", "")
    redis_url = os.environ.get("TEST_REDIS_URL", "")
    if not database_url or not redis_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("Les URL PostgreSQL et Redis sont obligatoires dans cet environnement.")
        pytest.skip("TEST_DATABASE_URL et TEST_REDIS_URL sont requis pour ce test d’intégration.")
    return database_url, redis_url


def migration_database_url() -> str:
    database_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not database_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_MIGRATION_DATABASE_URL est obligatoire dans cet environnement.")
        pytest.skip("TEST_MIGRATION_DATABASE_URL est requis pour ce test d’intégration.")
    return database_url


async def test_real_postgresql_and_redis_are_ready() -> None:
    database_url, redis_url = dependency_urls()
    database = PostgresDatabase(
        database_url,
        connect_timeout_seconds=2,
        pool_size=2,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=2_000,
    )
    redis = RedisResource(redis_url, connect_timeout_seconds=2, max_connections=2)
    try:
        report = await CheckReadinessUseCase((database, redis)).execute()
    finally:
        await redis.close()
        await database.close()

    assert report.is_ready
    assert {dependency.name: dependency.state for dependency in report.dependencies} == {
        "postgresql": "ok",
        "redis": "ok",
    }


async def test_unit_of_work_rolls_back_uncommitted_transaction() -> None:
    dependency_urls()
    database_url = migration_database_url()
    database = PostgresDatabase(
        database_url,
        connect_timeout_seconds=2,
        pool_size=2,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=2_000,
    )
    table_name = f"phase_2_1_rollback_probe_{uuid4().hex}"
    try:
        async with database.unit_of_work() as unit_of_work:
            await unit_of_work.session.execute(text(f"CREATE TABLE {table_name} (id integer)"))

        async with database.engine.connect() as connection:
            result = await connection.scalar(text("SELECT to_regclass(:table_name)"), {"table_name": table_name})
    finally:
        await database.close()

    assert result is None


async def test_identity_migration_created_all_expected_tables_and_indexes() -> None:
    dependency_urls()
    database_url = migration_database_url()
    database = PostgresDatabase(
        database_url,
        connect_timeout_seconds=2,
        pool_size=2,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=2_000,
    )
    try:
        async with database.engine.connect() as connection:
            table_names = await connection.run_sync(lambda sync_connection: inspect(sync_connection).get_table_names())
            membership_indexes = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_indexes("memberships")
            )
            membership_columns = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_columns("memberships")
            )
            invitation_indexes = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_indexes("user_invitations")
            )
    finally:
        await database.close()

    assert {
        "organizations",
        "users",
        "memberships",
        "user_invitations",
        "invitation_delivery_attempts",
    }.issubset(table_names)
    assert "ix_memberships_user_id_status" in {index["name"] for index in membership_indexes}
    assert "uq_user_invitations_active_organization_email" in {index["name"] for index in invitation_indexes}
    created_by = next(column for column in membership_columns if column["name"] == "created_by")
    assert created_by["nullable"] is False


async def test_real_identity_login_session_and_logout_workflow() -> None:
    database_url, redis_url = dependency_urls()
    owner_database = PostgresDatabase(
        migration_database_url(),
        connect_timeout_seconds=2,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=2_000,
    )
    database = PostgresDatabase(
        database_url,
        connect_timeout_seconds=2,
        pool_size=2,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=2_000,
    )
    redis = RedisResource(redis_url, connect_timeout_seconds=2, max_connections=5)
    environment = f"identity-{uuid4().hex}"
    clock = SystemClock()
    password_hasher = Argon2PasswordHasher()
    sessions = RedisSessionStore(
        redis.client,
        environment=environment,
        idle_seconds=1_800,
        absolute_seconds=43_200,
    )
    limiter = RedisLoginRateLimiter(
        redis.client,
        environment=environment,
        window_seconds=900,
        pair_limit=5,
        address_limit=20,
        hmac_key=b"integration-test-rate-limit-key-32-bytes",
    )
    email = f"admin-{uuid4().hex}@example.ca"
    password = "mot-de-passe-integration-solide"
    user_id = None
    try:
        bootstrap = BootstrapPlatformAdministratorUseCase(
            database.identity_unit_of_work,
            password_hasher,
            clock,
        )
        results = await asyncio.gather(
            bootstrap.execute(email=email, display_name="Admin intégration", password=password),
            bootstrap.execute(
                email=f"second-{uuid4().hex}@example.ca",
                display_name="Second admin",
                password=password,
            ),
            return_exceptions=True,
        )
        created_users = [result for result in results if isinstance(result, UserIdentity)]
        conflicts = [result for result in results if isinstance(result, PlatformAdministratorAlreadyExists)]
        assert len(created_users) == 1
        assert len(conflicts) == 1
        user = created_users[0]
        email = user.email
        user_id = user.id

        login = LoginUseCase(
            database.identity_unit_of_work,
            password_hasher,
            sessions,
            limiter,
            clock,
        )
        outcome = await login.execute(email=email.upper(), password=password, client_address="192.0.2.10")
        keys = [key async for key in redis.client.scan_iter(match=f"prospect:{environment}:*")]

        current = await GetCurrentSessionUseCase(database.identity_unit_of_work, sessions, clock).execute(
            outcome.session.token
        )
        await LogoutUseCase(sessions, clock).execute(
            token=outcome.session.token,
            csrf_token=outcome.identity.csrf_token,
        )

        assert current.user.id == user.id
        assert keys
        assert all(outcome.session.token not in key.decode() for key in keys)
        assert all(email.casefold() not in key.decode().casefold() for key in keys)
        assert await sessions.load_and_touch(outcome.session.token, clock.now()) is None
    finally:
        if user_id is not None:
            async with owner_database.engine.begin() as connection:
                await connection.execute(delete(UserModel).where(UserModel.id == user_id))
            await sessions.revoke_user(user_id)
        await redis.close()
        await database.close()
        await owner_database.close()


async def test_real_redis_enforces_idle_absolute_and_login_limits() -> None:
    _, redis_url = dependency_urls()
    redis = RedisResource(redis_url, connect_timeout_seconds=2, max_connections=5)
    environment = f"session-{uuid4().hex}"
    sessions = RedisSessionStore(
        redis.client,
        environment=environment,
        idle_seconds=1_800,
        absolute_seconds=43_200,
    )
    limiter = RedisLoginRateLimiter(
        redis.client,
        environment=environment,
        window_seconds=900,
        pair_limit=2,
        address_limit=10,
        hmac_key=b"integration-test-rate-limit-key-32-bytes",
    )
    now = datetime.now(UTC).replace(microsecond=0)
    user_id = uuid4()
    try:
        idle_session = await sessions.create(user_id=user_id, active_organization_id=None, user_version=1, now=now)
        assert await sessions.load_and_touch(idle_session.token, now + timedelta(minutes=10)) is not None
        assert await sessions.load_and_touch(idle_session.token, now + timedelta(minutes=40)) is None

        absolute_session = await sessions.create(user_id=user_id, active_organization_id=None, user_version=1, now=now)
        for minutes in range(20, 720, 20):
            assert await sessions.load_and_touch(absolute_session.token, now + timedelta(minutes=minutes)) is not None
        assert await sessions.load_and_touch(absolute_session.token, now + timedelta(minutes=719)) is not None
        assert await sessions.load_and_touch(absolute_session.token, now + timedelta(hours=12)) is None

        corrupted_session = await sessions.create(user_id=user_id, active_organization_id=None, user_version=1, now=now)
        corrupted_hash = hashlib.sha256(corrupted_session.token.encode()).hexdigest()
        corrupted_key = f"prospect:{environment}:session:{corrupted_hash}"
        await redis.client.set(corrupted_key, b"not-json", ex=1_800)
        assert await sessions.load_and_touch(corrupted_session.token, now) is None

        current_session = await sessions.create(
            user_id=user_id,
            active_organization_id=None,
            user_version=1,
            now=now,
        )
        next_organization_id = uuid4()
        rotated = await sessions.rotate(
            current_token=current_session.token,
            user_id=user_id,
            active_organization_id=next_organization_id,
            user_version=2,
            now=now + timedelta(minutes=1),
        )
        assert await sessions.load_and_touch(current_session.token, now + timedelta(minutes=1)) is None
        rotated_record = await sessions.load_and_touch(rotated.token, now + timedelta(minutes=1))
        assert rotated_record is not None
        assert rotated_record.active_organization_id == next_organization_id
        assert rotated_record.user_version == 2

        first_failure = await limiter.record_failure(client_address="192.0.2.20", email_dimension="hash-me")
        second_failure = await limiter.record_failure(client_address="192.0.2.20", email_dimension="hash-me")
        blocked = await limiter.check(client_address="192.0.2.20", email_dimension="hash-me")
        await limiter.reset_after_success(client_address="192.0.2.20", email_dimension="hash-me")
        unblocked = await limiter.check(client_address="192.0.2.20", email_dimension="hash-me")
        limiter_keys = [key.decode() async for key in redis.client.scan_iter(match=f"prospect:{environment}:login:*")]

        assert not first_failure.blocked
        assert second_failure.blocked
        assert blocked.blocked and blocked.retry_after_seconds > 0
        assert not unblocked.blocked
        assert all("192.0.2.20" not in key and "hash-me" not in key for key in limiter_keys)
    finally:
        await sessions.revoke_user(user_id)
        await redis.close()


async def test_invitation_limit_is_global_per_token_and_redis_keys_are_pseudonymized() -> None:
    _, redis_url = dependency_urls()
    redis = RedisResource(redis_url, connect_timeout_seconds=2, max_connections=3)
    environment = f"invitation-{uuid4().hex}"
    limiter = RedisInvitationRateLimiter(
        redis.client,
        environment=environment,
        window_seconds=900,
        address_limit=30,
        token_limit=1,
        hmac_key=b"integration-test-rate-limit-key-32-bytes",
    )
    token_hash = "f" * 64
    try:
        first = await limiter.consume(client_address="192.0.2.30", token_hash=token_hash)
        second_address = await limiter.consume(client_address="198.51.100.20", token_hash=token_hash)
        keys = [key.decode() async for key in redis.client.scan_iter(match=f"prospect:{environment}:*")]
    finally:
        matching_keys = [key async for key in redis.client.scan_iter(match=f"prospect:{environment}:*")]
        if matching_keys:
            await redis.client.delete(*matching_keys)
        await redis.close()

    assert not first.blocked
    assert second_address.blocked
    assert keys
    assert all("192.0.2.30" not in key and "198.51.100.20" not in key and token_hash not in key for key in keys)
