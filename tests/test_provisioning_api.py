from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import InvitationInvalid
from backend.app.application.use_cases import LoginOutcome
from backend.app.application.use_cases.provisioning import PlatformOrganizationPage
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.identity import (
    AuthenticatedIdentity,
    CreatedSession,
    MembershipRole,
    PlatformRole,
    SessionRecord,
    UserIdentity,
    UserStatus,
)
from backend.app.domain.provisioning import (
    InvitationDeliveryStatus,
    InvitationPreview,
    InvitationProvisioningView,
    InvitationState,
    OrganizationProvisioningView,
    ProvisioningView,
)

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)


def authenticated_identity(*, platform: bool = True) -> AuthenticatedIdentity:
    user = UserIdentity(
        id=uuid4(),
        email="admin@example.ca",
        display_name="Administrateur",
        password_hash="not-serialized",
        status=UserStatus.ACTIVE,
        platform_role=PlatformRole.PLATFORM_ADMIN if platform else None,
        last_active_organization_id=None,
        version=1,
        memberships=(),
    )
    return AuthenticatedIdentity(user, None, "csrf-in-memory")


def provisioning_view(*, replayed: bool = False) -> ProvisioningView:
    return ProvisioningView(
        OrganizationProvisioningView(
            uuid4(), "Entreprise Exemple", "fr-CA", "America/Toronto", "provisioning", 1, NOW, None
        ),
        InvitationProvisioningView(
            uuid4(),
            "invitee@example.ca",
            MembershipRole.ADMIN,
            InvitationState.ACTIVE,
            InvitationDeliveryStatus.SENT,
            NOW + timedelta(days=3),
        ),
        replayed,
    )


class CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "current-session"
        return self.identity


class CreateOrganization:
    def __init__(self, result: ProvisioningView) -> None:
        self.result = result
        self.calls = []

    async def execute(self, **kwargs) -> ProvisioningView:
        if not kwargs["has_platform_capability"]:
            from backend.app.application.errors import InsufficientCapability

            raise InsufficientCapability
        self.calls.append(kwargs)
        return self.result


class ListOrganizations:
    def __init__(self, result: ProvisioningView) -> None:
        self.result = result

    async def execute(self, **kwargs) -> PlatformOrganizationPage:
        assert kwargs["limit"] == 25
        return PlatformOrganizationPage((self.result,), None)


class PreviewInvitation:
    def __init__(self, *, invalid: bool = False) -> None:
        self.invalid = invalid

    async def execute(self, **kwargs) -> InvitationPreview:
        if self.invalid:
            raise InvitationInvalid
        return InvitationPreview("Entreprise Exemple", MembershipRole.ADMIN, NOW + timedelta(days=3), False)


class AcceptInvitation:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity
        self.new_calls = 0

    async def execute_new_account(self, **kwargs) -> LoginOutcome:
        self.new_calls += 1
        record = SessionRecord(
            self.identity.user.id,
            None,
            NOW,
            NOW,
            NOW + timedelta(hours=12),
            self.identity.csrf_token,
            1,
        )
        return LoginOutcome(self.identity, CreatedSession("rotated-session-secret", record))


def api_app(
    identity: AuthenticatedIdentity,
    *,
    create: CreateOrganization | None = None,
    preview: PreviewInvitation | None = None,
    accept: AcceptInvitation | None = None,
):
    view = provisioning_view()
    return create_app(
        container=AppContainer(
            settings=Settings(cors_allowed_origins=("http://test",)),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            get_current_session=CurrentSession(identity),  # type: ignore[arg-type]
            create_organization=create,  # type: ignore[arg-type]
            list_platform_organizations=ListOrganizations(view),  # type: ignore[arg-type]
            preview_invitation=preview,  # type: ignore[arg-type]
            accept_invitation=accept,  # type: ignore[arg-type]
        )
    )


async def test_platform_creation_requires_session_origin_csrf_and_platform_capability() -> None:
    create = CreateOrganization(provisioning_view())
    payload = {
        "name": "Entreprise Exemple",
        "locale": "fr-CA",
        "timezone": "America/Toronto",
        "first_administrator_email": "invitee@example.ca",
        "creation_request_id": str(uuid4()),
    }
    app = api_app(authenticated_identity(), create=create)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        anonymous = await client.post("/api/platform/organizations", json=payload, headers={"Origin": "http://test"})
        client.cookies.set("prospect_session", "current-session")
        missing_csrf = await client.post("/api/platform/organizations", json=payload, headers={"Origin": "http://test"})
        created = await client.post(
            "/api/platform/organizations",
            json=payload,
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-in-memory"},
        )

    assert anonymous.status_code == 401
    assert missing_csrf.status_code == 403
    assert created.status_code == 201
    assert created.headers["cache-control"] == "no-store, max-age=0"
    assert created.json()["first_invitation"]["delivery_status"] == "sent"
    assert "token" not in created.text.casefold()

    forbidden_app = api_app(authenticated_identity(platform=False), create=create)
    async with AsyncClient(transport=ASGITransport(app=forbidden_app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "current-session")
        forbidden = await client.post(
            "/api/platform/organizations",
            json=payload,
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-in-memory"},
        )
    assert forbidden.status_code == 403


async def test_platform_replay_is_200_and_list_exposes_only_provisioning_metadata() -> None:
    replay = provisioning_view(replayed=True)
    app = api_app(authenticated_identity(), create=CreateOrganization(replay))
    payload = {
        "name": "Entreprise Exemple",
        "locale": "fr-CA",
        "timezone": "America/Toronto",
        "first_administrator_email": "invitee@example.ca",
        "creation_request_id": str(uuid4()),
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "current-session")
        replayed = await client.post(
            "/api/platform/organizations",
            json=payload,
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-in-memory"},
        )
        listed = await client.get("/api/platform/organizations")

    assert replayed.status_code == 200
    assert replayed.json()["replayed"] is True
    assert listed.status_code == 200
    assert set(listed.json()["items"][0]) == {"organization", "first_invitation", "replayed"}
    assert all(term not in listed.text for term in ("password", "token_hash", "delivery_attempt"))


async def test_public_preview_is_minimized_and_all_invalidity_is_generic() -> None:
    token = "A" * 43
    app = api_app(authenticated_identity(), preview=PreviewInvitation())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/auth/invitations/preview", json={"token": token}, headers={"Origin": "http://test"}
        )
    assert response.status_code == 200
    assert set(response.json()) == {"organization_name", "role", "expires_at", "existing_account"}
    assert "email" not in response.text
    assert token not in response.text

    invalid_app = api_app(authenticated_identity(), preview=PreviewInvitation(invalid=True))
    async with AsyncClient(transport=ASGITransport(app=invalid_app), base_url="http://test") as client:
        invalid = await client.post(
            "/api/auth/invitations/preview", json={"token": token}, headers={"Origin": "http://test"}
        )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invitation_invalid"
    assert token not in invalid.text

    malformed_values: list[object] = ["", "A" * 129, 123]
    async with AsyncClient(transport=ASGITransport(app=invalid_app), base_url="http://test") as client:
        malformed_responses = [
            await client.post(
                "/api/auth/invitations/preview",
                json={"token": malformed},
                headers={"Origin": "http://test"},
            )
            for malformed in malformed_values
        ]
    assert all(response.status_code == 400 for response in malformed_responses)
    assert all(response.json()["error"]["code"] == "invitation_invalid" for response in malformed_responses)


async def test_new_account_acceptance_installs_http_only_session_without_secret_in_body() -> None:
    identity = authenticated_identity(platform=False)
    accept = AcceptInvitation(identity)
    app = api_app(identity, accept=accept)
    token = "A" * 43
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/auth/invitations/accept",
            json={
                "token": token,
                "new_account": {"display_name": "Alex", "password": "mot-de-passe-tres-solide"},
            },
            headers={"Origin": "http://test"},
        )

    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "rotated-session-secret" not in response.text
    assert token not in response.text
    assert accept.new_calls == 1
