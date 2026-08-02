from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import timedelta
from uuid import UUID, uuid4

from ...domain.identity import AuthenticatedIdentity, MembershipIdentity, UserIdentity
from ...domain.organization import (
    CreateMemberInvitationCommand,
    MemberInvitationView,
    MemberView,
    OrganizationView,
    UpdateMembershipCommand,
    UpdateOrganizationCommand,
    validate_create_member_invitation,
    validate_update_membership,
    validate_update_organization,
)
from ...domain.provisioning import InvitationDeliveryStatus, InvitationMessage
from ..errors import (
    AuthenticationServiceUnavailable,
    IdempotencyKeyReused,
    InsufficientCapability,
    InvitationAlreadyAccepted,
    InvitationAlreadyPending,
    InvitationDeliveryFailed,
    InvitationDeliveryUnavailable,
    InvitationRateLimited,
    LastActiveAdministrator,
    MembershipAlreadyActive,
    MembershipReactivationRequired,
    MembershipVersionConflict,
    OrganizationAdministrationUnavailable,
    OrganizationNotActive,
    OrganizationResourceNotFound,
    OrganizationSwitchForbidden,
    OrganizationVersionConflict,
    ProvisioningOutcomeUnknown,
    SessionRotationFailed,
)
from ..ports import (
    Clock,
    CreateMemberInvitationResultCode,
    CursorCodec,
    IdentityUnitOfWorkFactory,
    InvitationDelivery,
    InvitationTokenGenerator,
    MemberInvitationMutationResultCode,
    OrganizationAdministrationGateway,
    SessionStore,
    SwitchOrganizationResultCode,
    UpdateMembershipResultCode,
    UpdateOrganizationResultCode,
)
from ..tenancy import ActorContext, TenantContext
from .authentication import LoginOutcome

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MemberPage:
    items: tuple[MemberView, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class MemberInvitationPage:
    items: tuple[MemberInvitationView, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class UpdateMemberOutcome:
    member: MemberView
    current_user_changed: bool


class GetOrganizationUseCase:
    def __init__(self, gateway: OrganizationAdministrationGateway) -> None:
        self._gateway = gateway

    async def execute(self, *, context: TenantContext, has_capability: bool) -> OrganizationView:
        _require_capability(has_capability)
        organization = await self._gateway.get_organization(context=context)
        if organization is None:
            raise OrganizationResourceNotFound
        return organization


class UpdateOrganizationUseCase:
    def __init__(self, gateway: OrganizationAdministrationGateway, clock: Clock) -> None:
        self._gateway = gateway
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        command: UpdateOrganizationCommand,
        has_capability: bool,
    ) -> OrganizationView:
        _require_capability(has_capability)
        result = await self._gateway.update_organization(
            context=context,
            command=validate_update_organization(command),
            now=self._clock.now(),
        )
        if result.code is UpdateOrganizationResultCode.NOT_FOUND:
            raise OrganizationResourceNotFound
        if result.code is UpdateOrganizationResultCode.VERSION_CONFLICT:
            raise OrganizationVersionConflict(result.current_version)
        if result.organization is None:
            raise OrganizationAdministrationUnavailable("L’organisation modifiée n’a pas pu être relue.")
        return result.organization


class ListMembersUseCase:
    def __init__(self, gateway: OrganizationAdministrationGateway, cursor_codec: CursorCodec) -> None:
        self._gateway = gateway
        self._cursor_codec = cursor_codec

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        cursor: str | None,
        limit: int,
    ) -> MemberPage:
        _require_capability(has_capability)
        _validate_limit(limit)
        after_created_at, after_id = self._cursor_codec.decode(cursor)
        rows = await self._gateway.list_members(
            context=context,
            after_created_at=after_created_at,
            after_id=after_id,
            limit=limit + 1,
        )
        items = rows[:limit]
        return MemberPage(items=items, next_cursor=_next_cursor(rows, items, limit, self._cursor_codec))


class UpdateMembershipUseCase:
    def __init__(
        self,
        gateway: OrganizationAdministrationGateway,
        sessions: SessionStore,
        clock: Clock,
    ) -> None:
        self._gateway = gateway
        self._sessions = sessions
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        membership_id: UUID,
        command: UpdateMembershipCommand,
        has_capability: bool,
    ) -> UpdateMemberOutcome:
        _require_capability(has_capability)
        result = await self._gateway.update_membership(
            context=context,
            membership_id=membership_id,
            command=validate_update_membership(command),
            now=self._clock.now(),
        )
        if result.code is UpdateMembershipResultCode.NOT_FOUND:
            raise OrganizationResourceNotFound
        if result.code is UpdateMembershipResultCode.VERSION_CONFLICT:
            raise MembershipVersionConflict(result.current_version)
        if result.code is UpdateMembershipResultCode.LAST_ACTIVE_ADMINISTRATOR:
            raise LastActiveAdministrator
        if result.member is None:
            raise OrganizationAdministrationUnavailable("L’appartenance modifiée n’a pas pu être relue.")
        if result.code is UpdateMembershipResultCode.UPDATED:
            if result.user_version is None:
                raise OrganizationAdministrationUnavailable("La version de sécurité du membre est absente.")
            try:
                await self._sessions.revoke_user_before_version(result.member.user_id, result.user_version)
            except AuthenticationServiceUnavailable:
                LOGGER.warning(
                    "La purge des sessions antérieures a échoué.",
                    extra={
                        "request_id": context.request_id,
                        "user_id": str(result.member.user_id),
                        "minimum_valid_version": result.user_version,
                    },
                )
        return UpdateMemberOutcome(
            member=result.member,
            current_user_changed=(
                result.code is UpdateMembershipResultCode.UPDATED and result.member.user_id == context.actor_id
            ),
        )


class ListMemberInvitationsUseCase:
    def __init__(
        self,
        gateway: OrganizationAdministrationGateway,
        clock: Clock,
        cursor_codec: CursorCodec,
    ) -> None:
        self._gateway = gateway
        self._clock = clock
        self._cursor_codec = cursor_codec

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        cursor: str | None,
        limit: int,
    ) -> MemberInvitationPage:
        _require_capability(has_capability)
        _validate_limit(limit)
        after_created_at, after_id = self._cursor_codec.decode(cursor)
        rows = await self._gateway.list_invitations(
            context=context,
            after_created_at=after_created_at,
            after_id=after_id,
            limit=limit + 1,
            now=self._clock.now(),
        )
        items = rows[:limit]
        return MemberInvitationPage(
            items=items,
            next_cursor=_next_cursor(rows, items, limit, self._cursor_codec),
        )


class CreateMemberInvitationUseCase:
    def __init__(
        self,
        gateway: OrganizationAdministrationGateway,
        token_generator: InvitationTokenGenerator,
        delivery: InvitationDelivery,
        clock: Clock,
        *,
        public_app_url: str,
        invitation_ttl_seconds: int,
    ) -> None:
        self._gateway = gateway
        self._token_generator = token_generator
        self._delivery = delivery
        self._clock = clock
        self._public_app_url = public_app_url.rstrip("/")
        self._invitation_ttl_seconds = invitation_ttl_seconds

    async def execute(
        self,
        *,
        context: TenantContext,
        command: CreateMemberInvitationCommand,
        has_capability: bool,
    ) -> MemberInvitationView:
        _require_capability(has_capability)
        if not self._delivery.is_configured:
            raise InvitationDeliveryUnavailable
        organization = await self._gateway.get_organization(context=context)
        if organization is None:
            raise OrganizationNotActive
        validated = validate_create_member_invitation(command)
        token = self._token_generator.generate()
        now = self._clock.now()
        result = await self._gateway.create_invitation(
            context=context,
            command=validated,
            token=token,
            invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(seconds=self._invitation_ttl_seconds),
            now=now,
        )
        if result.code is CreateMemberInvitationResultCode.IDEMPOTENCY_CONFLICT:
            raise IdempotencyKeyReused
        if result.code is CreateMemberInvitationResultCode.MEMBERSHIP_ALREADY_ACTIVE:
            raise MembershipAlreadyActive
        if result.code is CreateMemberInvitationResultCode.MEMBERSHIP_REACTIVATION_REQUIRED:
            raise MembershipReactivationRequired
        if result.code is CreateMemberInvitationResultCode.INVITATION_ALREADY_PENDING:
            raise InvitationAlreadyPending
        if result.code is CreateMemberInvitationResultCode.ORGANIZATION_NOT_ACTIVE:
            raise OrganizationNotActive
        if result.invitation is None:
            raise OrganizationAdministrationUnavailable("L’invitation créée est absente.")
        if result.code is CreateMemberInvitationResultCode.REPLAYED:
            return result.invitation
        if result.delivery_attempt_id is None:
            raise ProvisioningOutcomeUnknown
        return await _deliver(
            gateway=self._gateway,
            delivery=self._delivery,
            clock=self._clock,
            public_app_url=self._public_app_url,
            context=context,
            organization_name=organization.name,
            invitation=result.invitation,
            delivery_attempt_id=result.delivery_attempt_id,
            raw_token=token.raw,
        )


class ResendMemberInvitationUseCase:
    def __init__(
        self,
        gateway: OrganizationAdministrationGateway,
        token_generator: InvitationTokenGenerator,
        delivery: InvitationDelivery,
        clock: Clock,
        *,
        public_app_url: str,
        invitation_ttl_seconds: int,
        cooldown_seconds: int,
        window_seconds: int,
        max_per_window: int,
    ) -> None:
        self._gateway = gateway
        self._token_generator = token_generator
        self._delivery = delivery
        self._clock = clock
        self._public_app_url = public_app_url.rstrip("/")
        self._invitation_ttl_seconds = invitation_ttl_seconds
        self._cooldown_seconds = cooldown_seconds
        self._window_seconds = window_seconds
        self._max_per_window = max_per_window

    async def execute(
        self,
        *,
        context: TenantContext,
        invitation_id: UUID,
        resend_request_id: UUID,
        has_capability: bool,
    ) -> MemberInvitationView:
        _require_capability(has_capability)
        if not self._delivery.is_configured:
            raise InvitationDeliveryUnavailable
        organization = await self._gateway.get_organization(context=context)
        if organization is None:
            raise OrganizationNotActive
        now = self._clock.now()
        token = self._token_generator.generate()
        result = await self._gateway.resend_invitation(
            context=context,
            invitation_id=invitation_id,
            request_id=resend_request_id,
            token=token,
            replacement_invitation_id=uuid4(),
            delivery_attempt_id=uuid4(),
            expires_at=now + timedelta(seconds=self._invitation_ttl_seconds),
            now=now,
            cooldown_seconds=self._cooldown_seconds,
            window_seconds=self._window_seconds,
            max_per_window=self._max_per_window,
        )
        _raise_mutation_error(result.code, result.retry_after_seconds)
        if result.invitation is None:
            raise OrganizationAdministrationUnavailable("L’invitation renvoyée est absente.")
        if result.code is MemberInvitationMutationResultCode.REPLAYED:
            return result.invitation
        if result.delivery_attempt_id is None:
            raise ProvisioningOutcomeUnknown
        return await _deliver(
            gateway=self._gateway,
            delivery=self._delivery,
            clock=self._clock,
            public_app_url=self._public_app_url,
            context=context,
            organization_name=organization.name,
            invitation=result.invitation,
            delivery_attempt_id=result.delivery_attempt_id,
            raw_token=token.raw,
        )


class RevokeMemberInvitationUseCase:
    def __init__(self, gateway: OrganizationAdministrationGateway, clock: Clock) -> None:
        self._gateway = gateway
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        invitation_id: UUID,
        has_capability: bool,
    ) -> MemberInvitationView:
        _require_capability(has_capability)
        result = await self._gateway.revoke_invitation(
            context=context,
            invitation_id=invitation_id,
            now=self._clock.now(),
        )
        _raise_mutation_error(result.code, result.retry_after_seconds)
        if result.invitation is None:
            raise OrganizationAdministrationUnavailable("L’invitation révoquée est absente.")
        return result.invitation


class SwitchOrganizationUseCase:
    def __init__(
        self,
        gateway: OrganizationAdministrationGateway,
        identity_unit_of_work_factory: IdentityUnitOfWorkFactory,
        sessions: SessionStore,
        clock: Clock,
    ) -> None:
        self._gateway = gateway
        self._identity_unit_of_work_factory = identity_unit_of_work_factory
        self._sessions = sessions
        self._clock = clock

    async def execute(
        self,
        *,
        identity: AuthenticatedIdentity,
        current_session_token: str,
        membership_id: UUID,
        request_id: str,
    ) -> LoginOutcome:
        result = await self._gateway.switch_organization(
            context=ActorContext(identity.user.id, request_id),
            membership_id=membership_id,
            now=self._clock.now(),
        )
        if result.code is SwitchOrganizationResultCode.NOT_FOUND:
            raise OrganizationResourceNotFound
        if result.code is SwitchOrganizationResultCode.FORBIDDEN:
            raise OrganizationSwitchForbidden
        if result.organization_id is None or result.user_version is None:
            raise OrganizationAdministrationUnavailable("Le changement d’organisation est incomplet.")
        refreshed = await self._load_identity(identity.user.id)
        try:
            session = await self._sessions.rotate(
                current_token=current_session_token,
                user_id=identity.user.id,
                active_organization_id=result.organization_id,
                user_version=result.user_version,
                now=self._clock.now(),
            )
        except AuthenticationServiceUnavailable as error:
            raise SessionRotationFailed from error
        return LoginOutcome(
            identity=AuthenticatedIdentity(
                user=refreshed,
                active_membership=_active_membership(refreshed, result.organization_id),
                csrf_token=session.record.csrf_token,
            ),
            session=session,
        )

    async def _load_identity(self, user_id: UUID) -> UserIdentity:
        async with self._identity_unit_of_work_factory() as unit_of_work:
            identity = await unit_of_work.identities.get_by_id(user_id)
        if identity is None:
            raise OrganizationAdministrationUnavailable("L’identité n’a pas pu être relue.")
        return identity


async def _deliver(
    *,
    gateway: OrganizationAdministrationGateway,
    delivery: InvitationDelivery,
    clock: Clock,
    public_app_url: str,
    context: TenantContext,
    organization_name: str,
    invitation: MemberInvitationView,
    delivery_attempt_id: UUID,
    raw_token: str,
) -> MemberInvitationView:
    sent = True
    failure_code = None
    try:
        await delivery.send(
            InvitationMessage(
                recipient_email=invitation.recipient_email,
                organization_name=organization_name,
                role=invitation.role,
                expires_at=invitation.expires_at,
                invitation_link=f"{public_app_url}/accept-invitation#token={raw_token}",
            )
        )
    except InvitationDeliveryFailed:
        sent = False
        failure_code = "delivery_failed"
    try:
        await gateway.finalize_delivery(
            context=context,
            invitation_id=invitation.id,
            delivery_attempt_id=delivery_attempt_id,
            sent=sent,
            failure_code=failure_code,
            now=clock.now(),
        )
    except OrganizationAdministrationUnavailable as error:
        raise ProvisioningOutcomeUnknown from error
    return replace(
        invitation,
        delivery_status=InvitationDeliveryStatus.SENT if sent else InvitationDeliveryStatus.FAILED,
    )


def _raise_mutation_error(code: MemberInvitationMutationResultCode, retry_after_seconds: int) -> None:
    if code is MemberInvitationMutationResultCode.IDEMPOTENCY_CONFLICT:
        raise IdempotencyKeyReused
    if code is MemberInvitationMutationResultCode.NOT_FOUND:
        raise OrganizationResourceNotFound
    if code is MemberInvitationMutationResultCode.ALREADY_ACCEPTED:
        raise InvitationAlreadyAccepted
    if code is MemberInvitationMutationResultCode.RATE_LIMITED:
        raise InvitationRateLimited(retry_after_seconds)


def _require_capability(has_capability: bool) -> None:
    if not has_capability:
        raise InsufficientCapability


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= 100:
        raise ValueError("La limite doit être comprise entre 1 et 100.")


def _next_cursor[Item: (MemberView, MemberInvitationView)](
    rows: tuple[Item, ...],
    items: tuple[Item, ...],
    limit: int,
    cursor_codec: CursorCodec,
) -> str | None:
    if len(rows) <= limit or not items:
        return None
    last = items[-1]
    item_id = last.membership_id if isinstance(last, MemberView) else last.id
    return cursor_codec.encode(last.created_at, item_id)


def _active_membership(identity: UserIdentity, organization_id: UUID) -> MembershipIdentity:
    for membership in identity.memberships:
        if membership.organization_id == organization_id and membership.is_active:
            return membership
    raise OrganizationAdministrationUnavailable("L’appartenance active n’a pas pu être relue.")
