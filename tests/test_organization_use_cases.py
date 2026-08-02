from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from backend.app.application.errors import (
    AuthenticationServiceUnavailable,
    InsufficientCapability,
    SessionRotationFailed,
)
from backend.app.application.ports import (
    SwitchOrganizationGatewayResult,
    SwitchOrganizationResultCode,
    UpdateMembershipGatewayResult,
    UpdateMembershipResultCode,
)
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.organization import SwitchOrganizationUseCase, UpdateMembershipUseCase
from backend.app.domain.identity import (
    AuthenticatedIdentity,
    CreatedSession,
    MembershipIdentity,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    SessionRecord,
    UserIdentity,
    UserStatus,
)
from backend.app.domain.organization import MemberView, UpdateMembershipCommand

NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


class Clock:
    def now(self) -> datetime:
        return NOW


def member_view(*, user_id: UUID, role: MembershipRole = MembershipRole.MANAGER, version: int = 2) -> MemberView:
    return MemberView(
        membership_id=uuid4(),
        user_id=user_id,
        email="membre@example.ca",
        display_name="Membre",
        role=role,
        status=MembershipStatus.ACTIVE,
        version=version,
        created_at=NOW,
        updated_at=NOW,
    )


class Gateway:
    def __init__(
        self,
        *,
        update_result: UpdateMembershipGatewayResult | None = None,
        switch_result: SwitchOrganizationGatewayResult | None = None,
    ) -> None:
        self.update_result = update_result
        self.switch_result = switch_result
        self.switch_calls: list[tuple[UUID, UUID]] = []

    async def update_membership(self, **kwargs) -> UpdateMembershipGatewayResult:
        assert self.update_result is not None
        return self.update_result

    async def switch_organization(self, **kwargs) -> SwitchOrganizationGatewayResult:
        assert self.switch_result is not None
        self.switch_calls.append((kwargs["context"].actor_id, kwargs["membership_id"]))
        return self.switch_result


class Sessions:
    def __init__(self, *, fail_rotation: bool = False, fail_purge: bool = False) -> None:
        self.fail_rotation = fail_rotation
        self.fail_purge = fail_purge
        self.purges: list[tuple[UUID, int]] = []
        self.rotations: list[dict[str, object]] = []

    async def revoke_user_before_version(self, user_id: UUID, minimum_valid_version: int) -> None:
        if self.fail_purge:
            raise AuthenticationServiceUnavailable
        self.purges.append((user_id, minimum_valid_version))

    async def rotate(self, **kwargs) -> CreatedSession:
        if self.fail_rotation:
            raise AuthenticationServiceUnavailable
        self.rotations.append(kwargs)
        record = SessionRecord(
            user_id=kwargs["user_id"],
            active_organization_id=kwargs["active_organization_id"],
            issued_at=NOW,
            last_seen_at=NOW,
            absolute_expires_at=NOW + timedelta(hours=12),
            csrf_token="new-csrf",
            user_version=kwargs["user_version"],
        )
        return CreatedSession("new-session", record)


class IdentityRepository:
    def __init__(self, identity: UserIdentity) -> None:
        self.identity = identity

    async def get_by_id(self, user_id: UUID) -> UserIdentity | None:
        return self.identity if self.identity.id == user_id else None


class IdentityUnitOfWork:
    def __init__(self, identity: UserIdentity) -> None:
        self.identities = IdentityRepository(identity)

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback


class IdentityUnitOfWorkFactory:
    def __init__(self, identity: UserIdentity) -> None:
        self.identity = identity

    def __call__(self) -> IdentityUnitOfWork:
        return IdentityUnitOfWork(self.identity)


async def test_effective_member_change_purges_only_sessions_before_new_identity_version() -> None:
    actor_id = uuid4()
    target_id = uuid4()
    view = member_view(user_id=target_id)
    gateway = Gateway(
        update_result=UpdateMembershipGatewayResult(
            UpdateMembershipResultCode.UPDATED,
            member=view,
            user_version=7,
        )
    )
    sessions = Sessions()
    use_case = UpdateMembershipUseCase(gateway, sessions, Clock())  # type: ignore[arg-type]

    outcome = await use_case.execute(
        context=TenantContext(actor_id, uuid4(), "request-1"),
        membership_id=view.membership_id,
        command=UpdateMembershipCommand(version=1, role=MembershipRole.MANAGER),
        has_capability=True,
    )

    assert sessions.purges == [(target_id, 7)]
    assert outcome.current_user_changed is False


async def test_noop_member_change_does_not_purge_and_self_change_is_reported() -> None:
    actor_id = uuid4()
    unchanged = member_view(user_id=actor_id)
    gateway = Gateway(
        update_result=UpdateMembershipGatewayResult(UpdateMembershipResultCode.UNCHANGED, member=unchanged)
    )
    sessions = Sessions()
    use_case = UpdateMembershipUseCase(gateway, sessions, Clock())  # type: ignore[arg-type]

    outcome = await use_case.execute(
        context=TenantContext(actor_id, uuid4(), "request-2"),
        membership_id=unchanged.membership_id,
        command=UpdateMembershipCommand(version=2, status=MembershipStatus.ACTIVE),
        has_capability=True,
    )

    assert sessions.purges == []
    assert outcome.current_user_changed is False

    changed = member_view(user_id=actor_id, role=MembershipRole.SALES, version=3)
    gateway.update_result = UpdateMembershipGatewayResult(
        UpdateMembershipResultCode.UPDATED, member=changed, user_version=4
    )
    outcome = await use_case.execute(
        context=TenantContext(actor_id, uuid4(), "request-3"),
        membership_id=changed.membership_id,
        command=UpdateMembershipCommand(version=2, role=MembershipRole.SALES),
        has_capability=True,
    )
    assert outcome.current_user_changed is True


async def test_committed_membership_change_survives_best_effort_redis_purge_failure() -> None:
    view = member_view(user_id=uuid4())
    use_case = UpdateMembershipUseCase(
        Gateway(
            update_result=UpdateMembershipGatewayResult(UpdateMembershipResultCode.UPDATED, member=view, user_version=2)
        ),
        Sessions(fail_purge=True),
        Clock(),  # type: ignore[arg-type]
    )
    outcome = await use_case.execute(
        context=TenantContext(uuid4(), uuid4(), "request-4"),
        membership_id=view.membership_id,
        command=UpdateMembershipCommand(version=1, role=MembershipRole.MANAGER),
        has_capability=True,
    )
    assert outcome.member == view


async def test_member_change_requires_server_side_capability() -> None:
    view = member_view(user_id=uuid4())
    use_case = UpdateMembershipUseCase(
        Gateway(update_result=UpdateMembershipGatewayResult(UpdateMembershipResultCode.UNCHANGED, member=view)),
        Sessions(),
        Clock(),  # type: ignore[arg-type]
    )
    with pytest.raises(InsufficientCapability):
        await use_case.execute(
            context=TenantContext(uuid4(), uuid4(), "request-5"),
            membership_id=view.membership_id,
            command=UpdateMembershipCommand(version=1, role=MembershipRole.SALES),
            has_capability=False,
        )


def multi_organization_identity() -> tuple[AuthenticatedIdentity, MembershipIdentity]:
    user_id = uuid4()
    current = MembershipIdentity(
        uuid4(),
        uuid4(),
        "Organisation A",
        MembershipRole.ADMIN,
        MembershipStatus.ACTIVE,
        OrganizationStatus.ACTIVE,
        NOW,
    )
    target = MembershipIdentity(
        uuid4(),
        uuid4(),
        "Organisation B",
        MembershipRole.MANAGER,
        MembershipStatus.ACTIVE,
        OrganizationStatus.ACTIVE,
        NOW,
    )
    user = UserIdentity(
        user_id,
        "membre@example.ca",
        "Membre",
        "hash",
        UserStatus.ACTIVE,
        None,
        current.organization_id,
        5,
        (current, target),
    )
    return AuthenticatedIdentity(user, current, "old-csrf"), target


async def test_switch_organization_rotates_only_current_session_and_returns_new_csrf() -> None:
    authenticated, target = multi_organization_identity()
    gateway = Gateway(
        switch_result=SwitchOrganizationGatewayResult(
            SwitchOrganizationResultCode.SWITCHED,
            organization_id=target.organization_id,
            user_version=authenticated.user.version,
        )
    )
    sessions = Sessions()
    use_case = SwitchOrganizationUseCase(
        gateway,
        IdentityUnitOfWorkFactory(authenticated.user),
        sessions,
        Clock(),  # type: ignore[arg-type]
    )

    outcome = await use_case.execute(
        identity=authenticated,
        current_session_token="old-session",
        membership_id=target.id,
        request_id="request-6",
    )

    assert outcome.session.token == "new-session"
    assert outcome.identity.csrf_token == "new-csrf"
    assert outcome.identity.active_membership == target
    assert sessions.rotations[0]["current_token"] == "old-session"
    assert sessions.rotations[0]["active_organization_id"] == target.organization_id


async def test_switch_organization_fails_closed_when_session_rotation_fails() -> None:
    authenticated, target = multi_organization_identity()
    use_case = SwitchOrganizationUseCase(
        Gateway(
            switch_result=SwitchOrganizationGatewayResult(
                SwitchOrganizationResultCode.SWITCHED,
                organization_id=target.organization_id,
                user_version=authenticated.user.version,
            )
        ),
        IdentityUnitOfWorkFactory(authenticated.user),
        Sessions(fail_rotation=True),
        Clock(),  # type: ignore[arg-type]
    )
    with pytest.raises(SessionRotationFailed):
        await use_case.execute(
            identity=authenticated,
            current_session_token="old-session",
            membership_id=target.id,
            request_id="request-7",
        )
