from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import InsufficientCapability, MembershipVersionConflict
from backend.app.application.use_cases import LoginOutcome
from backend.app.application.use_cases.organization import (
    MemberInvitationPage,
    MemberPage,
    UpdateMemberOutcome,
)
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
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
from backend.app.domain.organization import MemberInvitationView, MemberView, OrganizationView
from backend.app.domain.provisioning import InvitationDeliveryStatus, InvitationState

NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


def identity(role: MembershipRole) -> AuthenticatedIdentity:
    organization_id = uuid4()
    user_id = uuid4()
    active = MembershipIdentity(
        uuid4(),
        organization_id,
        "Entreprise Exemple",
        role,
        MembershipStatus.ACTIVE,
        OrganizationStatus.ACTIVE,
        NOW,
    )
    user = UserIdentity(
        user_id,
        f"{role.value}@example.ca",
        role.value.title(),
        "hash",
        UserStatus.ACTIVE,
        None,
        organization_id,
        1,
        (active,),
    )
    return AuthenticatedIdentity(user, active, "csrf-current")


def organization(authenticated: AuthenticatedIdentity) -> OrganizationView:
    assert authenticated.active_membership is not None
    return OrganizationView(
        authenticated.active_membership.organization_id,
        "Entreprise Exemple",
        "fr-CA",
        "America/Toronto",
        "active",
        2,
        NOW,
        NOW,
    )


def member(authenticated: AuthenticatedIdentity) -> MemberView:
    assert authenticated.active_membership is not None
    return MemberView(
        authenticated.active_membership.id,
        authenticated.user.id,
        authenticated.user.email,
        authenticated.user.display_name,
        authenticated.active_membership.role,
        authenticated.active_membership.status,
        1,
        NOW,
        NOW,
    )


class CurrentSession:
    def __init__(self, authenticated: AuthenticatedIdentity) -> None:
        self.authenticated = authenticated

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "current-session"
        return self.authenticated


def require(value: bool) -> None:
    if not value:
        raise InsufficientCapability


class GetOrganization:
    def __init__(self, view: OrganizationView) -> None:
        self.view = view

    async def execute(self, **kwargs) -> OrganizationView:
        require(kwargs["has_capability"])
        return self.view


class UpdateOrganization:
    def __init__(self, view: OrganizationView) -> None:
        self.view = view

    async def execute(self, **kwargs) -> OrganizationView:
        require(kwargs["has_capability"])
        return self.view


class ListMembers:
    def __init__(self, view: MemberView) -> None:
        self.view = view

    async def execute(self, **kwargs) -> MemberPage:
        require(kwargs["has_capability"])
        return MemberPage((self.view,), None)


class UpdateMembership:
    def __init__(self, view: MemberView, *, conflict: bool = False, self_change: bool = False) -> None:
        self.view = view
        self.conflict = conflict
        self.self_change = self_change

    async def execute(self, **kwargs) -> UpdateMemberOutcome:
        require(kwargs["has_capability"])
        if self.conflict:
            raise MembershipVersionConflict(4)
        return UpdateMemberOutcome(self.view, self.self_change)


class ListInvitations:
    def __init__(self) -> None:
        self.view = MemberInvitationView(
            uuid4(),
            "invitee@example.ca",
            MembershipRole.MANAGER,
            InvitationState.ACTIVE,
            InvitationDeliveryStatus.SENT,
            NOW + timedelta(days=3),
            NOW,
        )

    async def execute(self, **kwargs) -> MemberInvitationPage:
        require(kwargs["has_capability"])
        return MemberInvitationPage((self.view,), None)


class SwitchOrganization:
    def __init__(self, authenticated: AuthenticatedIdentity) -> None:
        self.authenticated = authenticated

    async def execute(self, **kwargs) -> LoginOutcome:
        assert kwargs["current_session_token"] == "current-session"
        record = SessionRecord(
            self.authenticated.user.id,
            self.authenticated.active_membership.organization_id if self.authenticated.active_membership else None,
            NOW,
            NOW,
            NOW + timedelta(hours=12),
            "csrf-rotated",
            self.authenticated.user.version,
        )
        rotated = AuthenticatedIdentity(
            self.authenticated.user,
            self.authenticated.active_membership,
            "csrf-rotated",
        )
        return LoginOutcome(rotated, CreatedSession("rotated-session", record))


def api_app(
    authenticated: AuthenticatedIdentity,
    *,
    update_member: UpdateMembership | None = None,
) -> object:
    org = organization(authenticated)
    member_view = member(authenticated)
    return create_app(
        container=AppContainer(
            settings=Settings(cors_allowed_origins=("http://test",)),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            get_current_session=CurrentSession(authenticated),  # type: ignore[arg-type]
            get_organization=GetOrganization(org),  # type: ignore[arg-type]
            update_organization=UpdateOrganization(org),  # type: ignore[arg-type]
            list_members=ListMembers(member_view),  # type: ignore[arg-type]
            update_membership=update_member or UpdateMembership(member_view),  # type: ignore[arg-type]
            list_member_invitations=ListInvitations(),  # type: ignore[arg-type]
            switch_organization=SwitchOrganization(authenticated),  # type: ignore[arg-type]
        )
    )


async def client_for(authenticated: AuthenticatedIdentity) -> AsyncClient:
    client = AsyncClient(transport=ASGITransport(app=api_app(authenticated)), base_url="http://test")
    client.cookies.set("prospect_session", "current-session")
    return client


async def test_administrator_can_read_and_mutate_tenant_resources_with_no_store() -> None:
    authenticated = identity(MembershipRole.ADMIN)
    async with await client_for(authenticated) as client:
        read = await client.get("/api/organization")
        updated = await client.patch(
            "/api/organization",
            json={"name": "Entreprise Exemple", "version": 2},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-current"},
        )
        members = await client.get("/api/organization/members")
        invitations = await client.get("/api/organization/invitations")

    assert (read.status_code, updated.status_code, members.status_code, invitations.status_code) == (200, 200, 200, 200)
    assert all(
        response.headers["cache-control"] == "no-store, max-age=0" for response in (read, updated, members, invitations)
    )
    assert set(members.json()["items"][0]) == {
        "membership_id",
        "user",
        "role",
        "status",
        "version",
        "created_at",
        "updated_at",
    }


async def test_manager_is_read_only_and_sales_cannot_read_members_or_invitations() -> None:
    manager = identity(MembershipRole.MANAGER)
    async with await client_for(manager) as client:
        members = await client.get("/api/organization/members")
        update = await client.patch(
            "/api/organization",
            json={"name": "Interdit", "version": 2},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-current"},
        )
        invitations = await client.get("/api/organization/invitations")
    assert (members.status_code, update.status_code, invitations.status_code) == (200, 403, 403)

    sales = identity(MembershipRole.SALES)
    async with await client_for(sales) as client:
        org = await client.get("/api/organization")
        members = await client.get("/api/organization/members")
        invitations = await client.get("/api/organization/invitations")
    assert (org.status_code, members.status_code, invitations.status_code) == (200, 403, 403)


async def test_strict_commands_reject_organization_id_and_version_conflict_is_minimized() -> None:
    authenticated = identity(MembershipRole.ADMIN)
    conflict_app = api_app(
        authenticated,
        update_member=UpdateMembership(member(authenticated), conflict=True),
    )
    async with AsyncClient(transport=ASGITransport(app=conflict_app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "current-session")
        injected = await client.patch(
            "/api/organization",
            json={"name": "Exemple", "version": 2, "organization_id": str(uuid4())},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-current"},
        )
        conflict = await client.patch(
            f"/api/organization/members/{authenticated.active_membership.id}",
            json={"role": "manager", "version": 1},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-current"},
        )
    assert injected.status_code == 422
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "membership_version_conflict"
    assert conflict.json()["error"]["fields"] == {"version": "4"}


async def test_self_privilege_change_expires_cookie_and_switch_rotates_it() -> None:
    authenticated = identity(MembershipRole.ADMIN)
    self_change_app = api_app(
        authenticated,
        update_member=UpdateMembership(member(authenticated), self_change=True),
    )
    async with AsyncClient(transport=ASGITransport(app=self_change_app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "current-session")
        changed = await client.patch(
            f"/api/organization/members/{authenticated.active_membership.id}",
            json={"role": "manager", "version": 1},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-current"},
        )
        client.cookies.set("prospect_session", "current-session")
        switched = await client.post(
            "/api/auth/switch-organization",
            json={"membership_id": str(authenticated.active_membership.id)},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-current"},
        )

    assert changed.status_code == 200
    assert "Max-Age=0" in changed.headers["set-cookie"]
    assert switched.status_code == 200
    assert "rotated-session" in switched.headers["set-cookie"]
    assert switched.json()["csrf_token"] == "csrf-rotated"
