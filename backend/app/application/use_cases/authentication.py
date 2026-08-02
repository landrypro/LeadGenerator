from __future__ import annotations

import hmac
from dataclasses import dataclass
from uuid import UUID

from ...domain.identity import (
    AuthenticatedIdentity,
    CreatedSession,
    InvalidEmail,
    MembershipIdentity,
    UserIdentity,
    normalize_email,
    select_active_organization,
)
from ..errors import (
    AuthenticationRequired,
    CsrfValidationFailed,
    InvalidCredentials,
    LoginRateLimited,
)
from ..ports import (
    Clock,
    IdentityUnitOfWorkFactory,
    LoginRateLimiter,
    PasswordHasher,
    SessionStore,
)


@dataclass(frozen=True, slots=True)
class LoginOutcome:
    identity: AuthenticatedIdentity
    session: CreatedSession


class LoginUseCase:
    def __init__(
        self,
        unit_of_work_factory: IdentityUnitOfWorkFactory,
        password_hasher: PasswordHasher,
        session_store: SessionStore,
        rate_limiter: LoginRateLimiter,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._password_hasher = password_hasher
        self._session_store = session_store
        self._rate_limiter = rate_limiter
        self._clock = clock

    async def execute(self, *, email: str, password: str, client_address: str) -> LoginOutcome:
        try:
            normalized_email = normalize_email(email).normalized
            email_is_valid = True
        except InvalidEmail:
            normalized_email = email
            email_is_valid = False

        limit = await self._rate_limiter.check(
            client_address=client_address,
            email_dimension=normalized_email,
        )
        if limit.blocked:
            raise LoginRateLimited(limit.retry_after_seconds)

        user: UserIdentity | None = None
        if email_is_valid:
            async with self._unit_of_work_factory() as unit_of_work:
                user = await unit_of_work.identities.get_by_normalized_email(normalized_email)

        verified = False
        if user is not None and user.password_hash is not None:
            verified = await self._password_hasher.verify(password, user.password_hash)
        else:
            await self._password_hasher.verify_dummy(password)

        active_organization_id = select_active_organization(user) if user is not None else None
        account_can_login = bool(user is not None and user.is_active)
        if not verified or not account_can_login or user is None:
            failure_limit = await self._rate_limiter.record_failure(
                client_address=client_address,
                email_dimension=normalized_email,
            )
            if failure_limit.blocked:
                raise LoginRateLimited(failure_limit.retry_after_seconds)
            raise InvalidCredentials

        now = self._clock.now()
        encoded_hash = user.password_hash
        if encoded_hash is None:
            raise InvalidCredentials
        replacement_hash = (
            await self._password_hasher.hash(password)
            if await self._password_hasher.needs_rehash(encoded_hash)
            else None
        )
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.identities.record_successful_login(user.id, now, replacement_hash)
            await unit_of_work.commit()

        await self._rate_limiter.reset_after_success(
            client_address=client_address,
            email_dimension=normalized_email,
        )
        created_session = await self._session_store.create(
            user_id=user.id,
            active_organization_id=active_organization_id,
            user_version=user.version,
            now=now,
        )
        active_membership = _find_active_membership(user, active_organization_id)
        return LoginOutcome(
            identity=AuthenticatedIdentity(
                user=user,
                active_membership=active_membership,
                csrf_token=created_session.record.csrf_token,
            ),
            session=created_session,
        )


class GetCurrentSessionUseCase:
    def __init__(
        self,
        unit_of_work_factory: IdentityUnitOfWorkFactory,
        session_store: SessionStore,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._session_store = session_store
        self._clock = clock

    async def execute(self, token: str) -> AuthenticatedIdentity:
        session = await self._session_store.load_and_touch(token, self._clock.now())
        if session is None:
            raise AuthenticationRequired

        async with self._unit_of_work_factory() as unit_of_work:
            user = await unit_of_work.identities.get_by_id(session.user_id)

        active_membership = _find_active_membership(user, session.active_organization_id) if user is not None else None
        valid = bool(
            user is not None
            and user.is_active
            and user.version == session.user_version
            and (active_membership is not None or session.active_organization_id is None)
        )
        if not valid or user is None:
            await self._session_store.revoke(token)
            raise AuthenticationRequired
        return AuthenticatedIdentity(
            user=user,
            active_membership=active_membership,
            csrf_token=session.csrf_token,
        )


class LogoutUseCase:
    def __init__(self, session_store: SessionStore, clock: Clock) -> None:
        self._session_store = session_store
        self._clock = clock

    async def execute(self, *, token: str, csrf_token: str) -> None:
        session = await self._session_store.load_and_touch(token, self._clock.now())
        if session is None:
            raise AuthenticationRequired
        if not hmac.compare_digest(session.csrf_token, csrf_token):
            raise CsrfValidationFailed
        await self._session_store.revoke(token)


def _find_active_membership(
    user: UserIdentity | None,
    organization_id: UUID | None,
) -> MembershipIdentity | None:
    if user is None or organization_id is None:
        return None
    return next(
        (
            membership
            for membership in user.memberships
            if membership.organization_id == organization_id and membership.is_active
        ),
        None,
    )
