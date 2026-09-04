from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import InsufficientCapability
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.identity import (
    AuthenticatedIdentity,
    MembershipIdentity,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    UserIdentity,
    UserStatus,
)
from backend.app.domain.prospect import (
    ContactChannelType,
    ContactChannelView,
    ProvenanceSourceKind,
    SourceProviderStatus,
    SourceProviderView,
)

CSRF_TOKEN = "csrf-compliance-api"
SESSION_TOKEN = "compliance-api-session"
NOW = datetime(2026, 8, 14, 16, tzinfo=UTC)


def identity(role: MembershipRole = MembershipRole.ADMIN) -> AuthenticatedIdentity:
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=uuid4(),
        organization_name="Entreprise QA",
        role=role,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=NOW,
    )
    user = UserIdentity(
        id=uuid4(),
        email="admin@example.ca",
        display_name="Admin QA",
        password_hash="not-serialized",
        status=UserStatus.ACTIVE,
        platform_role=None,
        last_active_organization_id=membership.organization_id,
        version=1,
        memberships=(membership,),
    )
    return AuthenticatedIdentity(user=user, active_membership=membership, csrf_token=CSRF_TOKEN)


class CurrentSession:
    def __init__(self, authenticated_identity: AuthenticatedIdentity) -> None:
        self.identity = authenticated_identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == SESSION_TOKEN
        return self.identity


class CreateSourceProviderStub:
    def __init__(self, organization_id) -> None:
        self.organization_id = organization_id
        self.calls: list[dict[str, object]] = []

    async def execute(
        self,
        *,
        context: object,
        has_capability: bool,
        source_kind: ProvenanceSourceKind,
        label: str,
    ) -> SourceProviderView:
        self.calls.append(
            {
                "context": context,
                "has_capability": has_capability,
                "source_kind": source_kind,
                "label": label,
            }
        )
        if not has_capability:
            raise InsufficientCapability
        return SourceProviderView(
            id=uuid4(),
            organization_id=self.organization_id,
            source_kind=source_kind,
            label=label,
            status=SourceProviderStatus.DRAFT,
            terms_reference=None,
            terms_url=None,
            valid_from=None,
            valid_until=None,
            allowed_territories=(),
            allowed_purposes=(),
            allowed_data_categories=(),
            rights_attested_at=None,
            rights_attested_by=None,
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )


def app_with_provider_route(role: MembershipRole = MembershipRole.ADMIN):
    authenticated = identity(role)
    membership = authenticated.active_membership
    assert membership is not None
    stub = CreateSourceProviderStub(membership.organization_id)
    container = AppContainer(
        settings=Settings(cors_allowed_origins=("http://test",)),
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=CurrentSession(authenticated),  # type: ignore[arg-type]
        create_source_provider=stub,  # type: ignore[arg-type]
    )
    return create_app(container=container), stub


async def test_create_source_provider_uses_capability_csrf_and_no_store() -> None:
    app, stub = app_with_provider_route()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.post(
            "/api/source-providers",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
            json={"source_kind": "csv", "label": "CSV client"},
        )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["status"] == "draft"
    assert stub.calls[0]["has_capability"] is True
    assert stub.calls[0]["source_kind"] is ProvenanceSourceKind.CSV


async def test_sales_cannot_manage_source_provider() -> None:
    app, _stub = app_with_provider_route(MembershipRole.SALES)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.post(
            "/api/source-providers",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
            json={"source_kind": "csv", "label": "CSV client"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_capability"


class ListChannelsStub:
    def __init__(self, organization_id) -> None:
        self.organization_id = organization_id
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs: object) -> tuple[ContactChannelView, ...]:
        self.calls.append(kwargs)
        if not kwargs["has_capability"]:
            raise InsufficientCapability
        target_id = kwargs.get("prospect_id") or kwargs.get("contact_id")
        return (
            ContactChannelView(
                id=uuid4(),
                organization_id=self.organization_id,
                channel_type=ContactChannelType.EMAIL,
                value="contact@example.ca",
                value_normalized="contact@example.ca",
                provenance_id=uuid4(),
                prospect_id=target_id if "prospect_id" in kwargs else None,
                contact_id=target_id if "contact_id" in kwargs else None,
                purpose="commercial_follow_up",
                version=1,
                archived_at=None,
            ),
        )


def app_with_channel_list_routes():
    authenticated = identity()
    membership = authenticated.active_membership
    assert membership is not None
    prospect_stub = ListChannelsStub(membership.organization_id)
    contact_stub = ListChannelsStub(membership.organization_id)
    container = AppContainer(
        settings=Settings(cors_allowed_origins=("http://test",)),
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=CurrentSession(authenticated),  # type: ignore[arg-type]
        list_prospect_channels=prospect_stub,  # type: ignore[arg-type]
        list_contact_channels=contact_stub,  # type: ignore[arg-type]
    )
    return create_app(container=container), prospect_stub, contact_stub


async def test_channel_lists_are_tenant_protected_and_never_cached() -> None:
    app, prospect_stub, contact_stub = app_with_channel_list_routes()
    prospect_id, contact_id = uuid4(), uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        prospect_response = await client.get(f"/api/prospects/{prospect_id}/channels")
        contact_response = await client.get(f"/api/contacts/{contact_id}/channels")

    assert prospect_response.status_code == 200
    assert contact_response.status_code == 200
    assert prospect_response.headers["cache-control"] == "no-store, max-age=0"
    assert contact_response.headers["cache-control"] == "no-store, max-age=0"
    assert prospect_response.json()[0]["value"] == "contact@example.ca"
    assert prospect_stub.calls[0]["has_capability"] is True
    assert contact_stub.calls[0]["has_capability"] is True
