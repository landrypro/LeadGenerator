from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4

from ...domain.identity import AuthenticatedIdentity, MembershipIdentity, UserIdentity, validate_new_password
from ...domain.provisioning import AcceptedInvitation, InvitationPreview, hash_invitation_token
from ..errors import (
    AuthenticationServiceUnavailable,
    InvitationAccountMismatch,
    InvitationAuthenticationRequired,
    InvitationInvalid,
    InvitationRateLimited,
    MembershipReactivationRequired,
    SessionCreationFailedAfterAcceptance,
)
from ..ports import (
    Clock,
    IdentityUnitOfWorkFactory,
    InvitationAcceptanceGateway,
    InvitationRateLimiter,
    PasswordHasher,
    SessionStore,
)
from ..ports.provisioning import AcceptanceGatewayResult, AcceptanceResultCode
from ..tenancy import ActorContext
from .authentication import LoginOutcome


class PreviewInvitationUseCase:
    def __init__(
        self,
        gateway: InvitationAcceptanceGateway,
        rate_limiter: InvitationRateLimiter,
        clock: Clock,
    ) -> None:
        self._gateway = gateway
        self._rate_limiter = rate_limiter
        self._clock = clock

    async def execute(self, *, token: str, client_address: str) -> InvitationPreview:
        token_hash, valid_format = _token_hash(token)
        await _consume_limit(self._rate_limiter, client_address, token_hash)
        if not valid_format:
            raise InvitationInvalid
        preview = await self._gateway.preview(token_hash=token_hash, now=self._clock.now())
        if preview is None:
            raise InvitationInvalid
        return preview


@dataclass(frozen=True, slots=True)
class NewAccountInvitationCommand:
    display_name: str
    password: str


class AcceptInvitationUseCase:
    def __init__(
        self,
        gateway: InvitationAcceptanceGateway,
        identity_unit_of_work_factory: IdentityUnitOfWorkFactory,
        password_hasher: PasswordHasher,
        sessions: SessionStore,
        rate_limiter: InvitationRateLimiter,
        clock: Clock,
    ) -> None:
        self._gateway = gateway
        self._identity_unit_of_work_factory = identity_unit_of_work_factory
        self._password_hasher = password_hasher
        self._sessions = sessions
        self._rate_limiter = rate_limiter
        self._clock = clock

    async def execute_new_account(
        self,
        *,
        token: str,
        command: NewAccountInvitationCommand,
        client_address: str,
    ) -> LoginOutcome:
        token_hash = await self._validated_limited_hash(token, client_address)
        display_name = " ".join(command.display_name.split())
        if not 1 <= len(display_name) <= 120:
            raise ValueError("Le nom affiché doit contenir entre 1 et 120 caractères.")
        validate_new_password(command.password)
        password_hash = await self._password_hasher.hash(command.password)
        result = await self._gateway.accept_new_account(
            token_hash=token_hash,
            user_id=uuid4(),
            membership_id=uuid4(),
            display_name=display_name,
            password_hash=password_hash,
            now=self._clock.now(),
        )
        accepted = _accepted_or_raise(result)
        identity = await self._load_identity(accepted.user_id)
        try:
            session = await self._sessions.create(
                user_id=accepted.user_id,
                active_organization_id=accepted.organization_id,
                user_version=accepted.user_version,
                now=self._clock.now(),
            )
        except AuthenticationServiceUnavailable as error:
            raise SessionCreationFailedAfterAcceptance from error
        return LoginOutcome(
            AuthenticatedIdentity(
                identity, _active_membership(identity, accepted.organization_id), session.record.csrf_token
            ),
            session,
        )

    async def execute_existing_account(
        self,
        *,
        token: str,
        identity: AuthenticatedIdentity,
        current_session_token: str,
        request_id: str,
        client_address: str,
    ) -> LoginOutcome:
        token_hash = await self._validated_limited_hash(token, client_address)
        result = await self._gateway.accept_existing_account(
            context=ActorContext(identity.user.id, request_id),
            token_hash=token_hash,
            membership_id=uuid4(),
            now=self._clock.now(),
        )
        accepted = _accepted_or_raise(result)
        refreshed = await self._load_identity(accepted.user_id)
        try:
            session = await self._sessions.rotate(
                current_token=current_session_token,
                user_id=accepted.user_id,
                active_organization_id=accepted.organization_id,
                user_version=accepted.user_version,
                now=self._clock.now(),
            )
        except AuthenticationServiceUnavailable as error:
            raise SessionCreationFailedAfterAcceptance from error
        return LoginOutcome(
            AuthenticatedIdentity(
                refreshed,
                _active_membership(refreshed, accepted.organization_id),
                session.record.csrf_token,
            ),
            session,
        )

    async def _validated_limited_hash(self, token: str, client_address: str) -> str:
        token_hash, valid_format = _token_hash(token)
        await _consume_limit(self._rate_limiter, client_address, token_hash)
        if not valid_format:
            raise InvitationInvalid
        return token_hash

    async def _load_identity(self, user_id: UUID) -> UserIdentity:
        async with self._identity_unit_of_work_factory() as unit_of_work:
            identity = await unit_of_work.identities.get_by_id(user_id)
        if identity is None:
            raise SessionCreationFailedAfterAcceptance
        return identity


async def _consume_limit(limiter: InvitationRateLimiter, client_address: str, token_hash: str) -> None:
    limit = await limiter.consume(client_address=client_address, token_hash=token_hash)
    if limit.blocked:
        raise InvitationRateLimited(limit.retry_after_seconds)


def _token_hash(token: str) -> tuple[str, bool]:
    fallback_hash = hashlib.sha256(token[:128].encode("utf-8", errors="replace")).hexdigest()
    try:
        return hash_invitation_token(token), True
    except ValueError:
        return fallback_hash, False


def _accepted_or_raise(result: AcceptanceGatewayResult) -> AcceptedInvitation:
    if result.code is AcceptanceResultCode.INVALID:
        raise InvitationInvalid
    if result.code is AcceptanceResultCode.EXISTING_ACCOUNT:
        raise InvitationAuthenticationRequired
    if result.code is AcceptanceResultCode.ACCOUNT_MISMATCH:
        raise InvitationAccountMismatch
    if result.code is AcceptanceResultCode.MEMBERSHIP_REACTIVATION_REQUIRED:
        raise MembershipReactivationRequired
    if result.accepted is None:
        raise InvitationInvalid
    return result.accepted


def _active_membership(identity: UserIdentity, organization_id: UUID) -> MembershipIdentity:
    for membership in identity.memberships:
        if membership.organization_id == organization_id and membership.is_active:
            return membership
    raise SessionCreationFailedAfterAcceptance
