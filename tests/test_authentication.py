from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from backend.app.application.errors import (
    AuthenticationRequired,
    CsrfValidationFailed,
    IdentityConcurrentUpdate,
    InvalidCredentials,
    PlatformAdministratorAlreadyExists,
    PlatformAdministratorNotFound,
)
from backend.app.application.ports import LoginLimitStatus
from backend.app.application.use_cases import (
    BootstrapPlatformAdministratorUseCase,
    GetCurrentSessionUseCase,
    LoginUseCase,
    LogoutUseCase,
    ResetPlatformAdministratorPasswordUseCase,
)
from backend.app.domain.identity import (
    CreatedSession,
    PlatformRole,
    SessionRecord,
    UserIdentity,
    UserStatus,
)

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakePasswordHasher:
    def __init__(self, accepted_password: str = "correct-password") -> None:
        self.accepted_password = accepted_password
        self.verified_hashes: list[str] = []
        self.dummy_verifications = 0

    async def hash(self, password: str) -> str:
        return f"hashed:{password}"

    async def verify(self, password: str, encoded_hash: str) -> bool:
        self.verified_hashes.append(encoded_hash)
        return password == self.accepted_password and encoded_hash == "existing-hash"

    async def verify_dummy(self, password: str) -> None:
        del password
        self.dummy_verifications += 1

    async def needs_rehash(self, encoded_hash: str) -> bool:
        del encoded_hash
        return False


class FakeIdentityRepository:
    def __init__(self, user: UserIdentity | None = None, *, platform_admin_exists: bool = False) -> None:
        self.user = user
        self.platform_admin_exists = platform_admin_exists
        self.login_recorded = False
        self.password_replacement_succeeds = True
        self.replacement: tuple[UUID, int, str, datetime] | None = None

    async def get_by_normalized_email(self, email_normalized: str) -> UserIdentity | None:
        return self.user if self.user and email_normalized == "admin@example.ca" else None

    async def get_by_id(self, user_id: UUID) -> UserIdentity | None:
        return self.user if self.user and self.user.id == user_id else None

    async def record_successful_login(
        self,
        user_id: UUID,
        occurred_at: datetime,
        replacement_password_hash: str | None,
    ) -> None:
        del user_id, occurred_at, replacement_password_hash
        self.login_recorded = True

    async def platform_administrator_exists(self) -> bool:
        return self.platform_admin_exists

    async def create_platform_administrator(
        self,
        *,
        email: str,
        email_normalized: str,
        display_name: str,
        password_hash: str,
        occurred_at: datetime,
    ) -> UserIdentity:
        del email_normalized, occurred_at
        self.user = platform_user(email=email, display_name=display_name, password_hash=password_hash)
        return self.user

    async def replace_platform_administrator_password(
        self,
        *,
        user_id: UUID,
        expected_version: int,
        password_hash: str,
        occurred_at: datetime,
    ) -> bool:
        self.replacement = (user_id, expected_version, password_hash, occurred_at)
        return self.password_replacement_succeeds


class FakeIdentityUnitOfWork:
    def __init__(self, identities: FakeIdentityRepository) -> None:
        self.identities = identities
        self.committed = False

    async def __aenter__(self) -> FakeIdentityUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


class FakeIdentityUnitOfWorkFactory:
    def __init__(self, identities: FakeIdentityRepository) -> None:
        self.unit_of_work = FakeIdentityUnitOfWork(identities)

    def __call__(self) -> FakeIdentityUnitOfWork:
        return self.unit_of_work


class FakeSessionStore:
    def __init__(self, record: SessionRecord | None = None) -> None:
        self.record = record
        self.revoked_tokens: list[str] = []

    async def create(
        self,
        *,
        user_id: UUID,
        active_organization_id: UUID | None,
        user_version: int,
        now: datetime,
    ) -> CreatedSession:
        self.record = SessionRecord(
            user_id=user_id,
            active_organization_id=active_organization_id,
            issued_at=now,
            last_seen_at=now,
            absolute_expires_at=now + timedelta(hours=12),
            csrf_token="csrf-token",
            user_version=user_version,
        )
        return CreatedSession(token="opaque-session-token", record=self.record)

    async def load_and_touch(self, token: str, now: datetime) -> SessionRecord | None:
        del token, now
        return self.record

    async def revoke(self, token: str) -> None:
        self.revoked_tokens.append(token)
        self.record = None

    async def revoke_user(self, user_id: UUID) -> None:
        del user_id
        self.record = None

    async def revoke_user_before_version(self, user_id: UUID, minimum_valid_version: int) -> None:
        del user_id
        if self.record is not None and self.record.user_version < minimum_valid_version:
            self.record = None


class FakeLoginRateLimiter:
    def __init__(self) -> None:
        self.failures = 0

    async def check(self, *, client_address: str, email_dimension: str) -> LoginLimitStatus:
        del client_address, email_dimension
        return LoginLimitStatus(blocked=False)

    async def record_failure(self, *, client_address: str, email_dimension: str) -> LoginLimitStatus:
        del client_address, email_dimension
        self.failures += 1
        return LoginLimitStatus(blocked=False)

    async def reset_after_success(self, *, client_address: str, email_dimension: str) -> None:
        del client_address, email_dimension


def platform_user(
    *,
    status: UserStatus = UserStatus.ACTIVE,
    email: str = "admin@example.ca",
    display_name: str = "Admin",
    password_hash: str = "existing-hash",
) -> UserIdentity:
    return UserIdentity(
        id=uuid4(),
        email=email,
        display_name=display_name,
        password_hash=password_hash,
        status=status,
        platform_role=PlatformRole.PLATFORM_ADMIN,
        last_active_organization_id=None,
        version=1,
        memberships=(),
    )


async def test_login_creates_opaque_session_for_active_platform_administrator() -> None:
    repository = FakeIdentityRepository(platform_user())
    sessions = FakeSessionStore()
    use_case = LoginUseCase(
        FakeIdentityUnitOfWorkFactory(repository),
        FakePasswordHasher(),
        sessions,
        FakeLoginRateLimiter(),
        FixedClock(),
    )

    outcome = await use_case.execute(
        email="ADMIN@example.ca",
        password="correct-password",
        client_address="127.0.0.1",
    )

    assert outcome.session.token == "opaque-session-token"
    assert outcome.identity.csrf_token == "csrf-token"
    assert repository.login_recorded


async def test_unknown_and_known_accounts_each_perform_one_password_verification_path() -> None:
    known_hasher = FakePasswordHasher()
    known = LoginUseCase(
        FakeIdentityUnitOfWorkFactory(FakeIdentityRepository(platform_user())),
        known_hasher,
        FakeSessionStore(),
        FakeLoginRateLimiter(),
        FixedClock(),
    )
    unknown_hasher = FakePasswordHasher()
    unknown_limiter = FakeLoginRateLimiter()
    unknown = LoginUseCase(
        FakeIdentityUnitOfWorkFactory(FakeIdentityRepository()),
        unknown_hasher,
        FakeSessionStore(),
        unknown_limiter,
        FixedClock(),
    )

    with pytest.raises(InvalidCredentials):
        await known.execute(email="admin@example.ca", password="incorrect", client_address="127.0.0.1")
    with pytest.raises(InvalidCredentials):
        await unknown.execute(email="unknown@example.ca", password="incorrect", client_address="127.0.0.1")

    assert len(known_hasher.verified_hashes) == 1
    assert unknown_hasher.dummy_verifications == 1
    assert unknown_limiter.failures == 1


async def test_disabled_user_invalidates_existing_session() -> None:
    user = platform_user(status=UserStatus.DISABLED)
    record = SessionRecord(user.id, None, NOW, NOW, NOW + timedelta(hours=12), "csrf-token", 1)
    sessions = FakeSessionStore(record)
    use_case = GetCurrentSessionUseCase(
        FakeIdentityUnitOfWorkFactory(FakeIdentityRepository(user)),
        sessions,
        FixedClock(),
    )

    with pytest.raises(AuthenticationRequired):
        await use_case.execute("session-token")

    assert sessions.revoked_tokens == ["session-token"]


async def test_logout_requires_matching_csrf_then_revokes_session() -> None:
    user = platform_user()
    sessions = FakeSessionStore(SessionRecord(user.id, None, NOW, NOW, NOW + timedelta(hours=12), "csrf-token", 1))
    use_case = LogoutUseCase(sessions, FixedClock())

    with pytest.raises(CsrfValidationFailed):
        await use_case.execute(token="session-token", csrf_token="wrong")
    await use_case.execute(token="session-token", csrf_token="csrf-token")

    assert sessions.revoked_tokens == ["session-token"]


async def test_platform_bootstrap_is_unique_and_validates_password_without_normalization() -> None:
    repository = FakeIdentityRepository()
    unit_of_work_factory = FakeIdentityUnitOfWorkFactory(repository)
    use_case = BootstrapPlatformAdministratorUseCase(
        unit_of_work_factory,
        FakePasswordHasher(),
        FixedClock(),
    )

    user = await use_case.execute(
        email="Admin@Example.ca",
        display_name="  Premier   Admin  ",
        password="mot-de-passe-solide",
    )
    repository.platform_admin_exists = True

    assert user.display_name == "Premier Admin"
    assert unit_of_work_factory.unit_of_work.committed
    with pytest.raises(PlatformAdministratorAlreadyExists):
        await use_case.execute(
            email="second@example.ca",
            display_name="Second",
            password="autre-mot-de-passe-solide",
        )


async def test_platform_admin_password_reset_hashes_updates_and_commits() -> None:
    user = platform_user()
    repository = FakeIdentityRepository(user)
    unit_of_work_factory = FakeIdentityUnitOfWorkFactory(repository)
    use_case = ResetPlatformAdministratorPasswordUseCase(
        unit_of_work_factory,
        FakePasswordHasher(),
        FixedClock(),
    )

    user_id = await use_case.execute(email="ADMIN@example.ca", password="nouveau-mot-de-passe")

    assert user_id == user.id
    assert repository.replacement == (user.id, user.version, "hashed:nouveau-mot-de-passe", NOW)
    assert unit_of_work_factory.unit_of_work.committed


async def test_platform_admin_password_reset_rejects_non_platform_account() -> None:
    regular_user = UserIdentity(
        id=uuid4(),
        email="admin@example.ca",
        display_name="Compte organisation",
        password_hash="existing-hash",
        status=UserStatus.ACTIVE,
        platform_role=None,
        last_active_organization_id=None,
        version=1,
        memberships=(),
    )
    repository = FakeIdentityRepository(regular_user)
    use_case = ResetPlatformAdministratorPasswordUseCase(
        FakeIdentityUnitOfWorkFactory(repository),
        FakePasswordHasher(),
        FixedClock(),
    )

    with pytest.raises(PlatformAdministratorNotFound):
        await use_case.execute(email="admin@example.ca", password="nouveau-mot-de-passe")

    assert repository.replacement is None


async def test_platform_admin_password_reset_detects_concurrent_update() -> None:
    repository = FakeIdentityRepository(platform_user())
    repository.password_replacement_succeeds = False
    use_case = ResetPlatformAdministratorPasswordUseCase(
        FakeIdentityUnitOfWorkFactory(repository),
        FakePasswordHasher(),
        FixedClock(),
    )

    with pytest.raises(IdentityConcurrentUpdate):
        await use_case.execute(email="admin@example.ca", password="nouveau-mot-de-passe")
