from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.identity import (
    AuthenticatedIdentity,
    MembershipRole,
    PlatformRole,
    UserIdentity,
    UserStatus,
)
from backend.app.domain.provisioning import (
    InvitationDeliveryStatus,
    InvitationProvisioningView,
    InvitationState,
    OrganizationProvisioningView,
    ProvisioningView,
)

NOW = datetime(2026, 8, 13, 12, tzinfo=UTC)


def platform_identity() -> AuthenticatedIdentity:
    user = UserIdentity(
        id=uuid4(),
        email="platform@example.ca",
        display_name="Plateforme",
        password_hash="hash",
        status=UserStatus.ACTIVE,
        platform_role=PlatformRole.PLATFORM_ADMIN,
        last_active_organization_id=None,
        version=1,
        memberships=(),
    )
    return AuthenticatedIdentity(user, None, "csrf-platform")


class CurrentSession:
    def __init__(self, authenticated: AuthenticatedIdentity) -> None:
        self.authenticated = authenticated

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "platform-session"
        return self.authenticated


class ChangeStatus:
    def __init__(self, status: str) -> None:
        self.status = status
        self.command = None

    async def execute(self, **kwargs) -> ProvisioningView:
        self.command = kwargs["command"]
        organization_id = kwargs["organization_id"]
        return ProvisioningView(
            OrganizationProvisioningView(
                organization_id,
                "Entreprise Exemple",
                "fr-CA",
                "America/Toronto",
                self.status,
                kwargs["command"].version + 1,
                NOW,
                NOW,
            ),
            InvitationProvisioningView(
                uuid4(),
                "admin@example.ca",
                MembershipRole.ADMIN,
                InvitationState.ACCEPTED,
                InvitationDeliveryStatus.SENT,
                NOW + timedelta(days=3),
            ),
            False,
        )


def app_for(use_case: ChangeStatus) -> object:
    return create_app(
        container=AppContainer(
            settings=Settings(cors_allowed_origins=("http://test",)),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            get_current_session=CurrentSession(platform_identity()),  # type: ignore[arg-type]
            suspend_organization=use_case,  # type: ignore[arg-type]
        )
    )


async def test_platform_suspend_route_uses_versioned_idempotent_command() -> None:
    use_case = ChangeStatus("suspended")
    organization_id = uuid4()
    app = app_for(use_case)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "platform-session")
        response = await client.post(
            f"/api/platform/organizations/{organization_id}/suspend",
            json={
                "operation_id": str(uuid4()),
                "version": 4,
                "reason_code": "administrative",
                "external_reference": "TICKET-123",
            },
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-platform"},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["organization"]["status"] == "suspended"
    assert use_case.command.version == 4
    assert use_case.command.external_reference == "TICKET-123"
