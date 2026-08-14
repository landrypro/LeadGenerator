import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import StaticMapProviderError
from backend.app.application.models import GooglePlaceSearchCriteria
from backend.app.application.ports.maps import MapImage
from backend.app.application.ports.places import PlaceCandidate
from backend.app.application.use_cases import GetMapSnapshotUseCase, SearchGooglePlacesUseCase
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.identity import (
    CAPABILITIES_BY_ROLE,
    AuthenticatedIdentity,
    MembershipIdentity,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    PlatformRole,
    UserIdentity,
    UserStatus,
)
from backend.app.infrastructure.memory import (
    InMemoryGenerationGuard,
    InMemoryGoogleSelectionGrantStore,
    InMemoryMapSnapshotGrantStore,
)

CSRF_TOKEN = "csrf-integration"
SESSION_TOKEN = "integration-session"


def authenticated_identity(
    *,
    organization_id=None,
    user_id=None,
    role: MembershipRole = MembershipRole.SALES,
) -> AuthenticatedIdentity:
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=organization_id or uuid4(),
        organization_name="Entreprise Intégration",
        role=role,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=datetime.now(UTC),
    )
    user = UserIdentity(
        id=user_id or uuid4(),
        email="sales@example.ca",
        display_name="Vente",
        password_hash="not-serialized",
        status=UserStatus.ACTIVE,
        platform_role=None,
        last_active_organization_id=membership.organization_id,
        version=1,
        memberships=(membership,),
    )
    return AuthenticatedIdentity(user, membership, CSRF_TOKEN)


class CurrentSession:
    def __init__(self, identities: dict[str, AuthenticatedIdentity]) -> None:
        self.identities = identities

    async def execute(self, token: str) -> AuthenticatedIdentity:
        return self.identities[token]


class FakePlacesGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, criteria: GooglePlaceSearchCriteria) -> list[PlaceCandidate]:
        self.calls += 1
        return [
            PlaceCandidate(
                place_id=f"place-integration-{index}",
                name=f"Entreprise {index}",
                address="100 rue Principale, Québec",
                google_maps_url=f"https://maps.google.com/?cid={index}",
                latitude=46.8139,
                longitude=-71.2080,
                primary_type="plumber",
                business_status="OPERATIONAL",
            )
            for index in range(25)
        ]


class FakeStaticMapGateway:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    async def fetch(self, payload: object) -> MapImage:
        self.calls += 1
        if self.fail:
            raise StaticMapProviderError(503, "provider-secret-must-not-leak")
        return MapImage(content=b"fake-png", media_type="image/png")


class BlockingPlacesGateway(FakePlacesGateway):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def search(self, criteria: GooglePlaceSearchCriteria) -> list[PlaceCandidate]:
        self.started.set()
        await self.release.wait()
        return await super().search(criteria)


def integration_app(
    *,
    identities=None,
    places_gateway: FakePlacesGateway | None = None,
    map_gateway: FakeStaticMapGateway | None = None,
) -> tuple[object, FakePlacesGateway]:
    settings = Settings(
        google_maps_api_key="test-places-key",
        google_maps_static_api_key="test-static-key",
        cors_allowed_origins=("http://test",),
    )
    places = places_gateway or FakePlacesGateway()
    maps = map_gateway or FakeStaticMapGateway()
    grants = InMemoryMapSnapshotGrantStore()
    selection_grants = InMemoryGoogleSelectionGrantStore()
    container = AppContainer(
        settings=settings,
        search_google_places=SearchGooglePlacesUseCase(
            places,
            InMemoryGenerationGuard(),
            grants,
            selection_grants,
        ),
        get_map_snapshot=GetMapSnapshotUseCase(grants, maps),
        get_current_session=CurrentSession(identities or {SESSION_TOKEN: authenticated_identity()}),  # type: ignore[arg-type]
    )
    return create_app(container=container), places


def search_payload() -> dict[str, object]:
    return {
        "query": "plombier",
        "center_latitude": 46.8139,
        "center_longitude": -71.2080,
        "radius_km": 10,
        "include_service_area_businesses": True,
        "language_code": "fr",
        "region_code": "CA",
    }


def authorize(client: AsyncClient, token: str = SESSION_TOKEN) -> dict[str, str]:
    client.cookies.set("prospect_session", token)
    return {"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN}


def identity_without_organization(*, platform: bool = False) -> AuthenticatedIdentity:
    user = UserIdentity(
        id=uuid4(),
        email="platform@example.ca" if platform else "orphan@example.ca",
        display_name="Sans organisation",
        password_hash="not-serialized",
        status=UserStatus.ACTIVE,
        platform_role=PlatformRole.PLATFORM_ADMIN if platform else None,
        last_active_organization_id=None,
        version=1,
        memberships=(),
    )
    return AuthenticatedIdentity(user, None, CSRF_TOKEN)


@pytest.mark.integration
async def test_limited_search_and_protected_map_workflow_through_http() -> None:
    app, places_gateway = integration_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = authorize(client)
        search_response = await client.post("/api/google/places/search", json=search_payload(), headers=headers)

        assert search_response.status_code == 200
        assert search_response.headers["cache-control"] == "no-store, max-age=0"
        body = search_response.json()
        assert places_gateway.calls == 1
        assert len(body["places"]) == 20
        assert body["stats"]["api_calls"] == 1
        assert body["search_parameters"]["radius_km"] == 10
        assert all("phone" not in place for place in body["places"])
        assert all("international_phone" not in place for place in body["places"])
        assert all("website" not in place for place in body["places"])

        token = body["map_snapshot_token"]
        map_response = await client.post("/api/map/snapshot", json={"token": token}, headers=headers)
        assert map_response.status_code == 200
        assert map_response.content == b"fake-png"
        assert map_response.headers["cache-control"] == "no-store, max-age=0"

        replay_response = await client.post("/api/map/snapshot", json={"token": token}, headers=headers)
        assert replay_response.status_code == 403


@pytest.mark.integration
async def test_historical_search_and_export_routes_are_absent() -> None:
    app, _ = integration_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        old_search = await client.post("/api/leads/search", json=search_payload())
        old_export = await client.post("/api/leads/export", json={"leads": [], "search": {}})
        schema = (await client.get("/openapi.json")).json()

    # Le montage statique de production peut répondre 405 à un POST inconnu ;
    # l'absence du chemin OpenAPI prouve qu'aucune route applicative ne subsiste.
    assert old_search.status_code in {404, 405}
    assert old_export.status_code in {404, 405}
    assert "/api/leads/search" not in schema["paths"]
    assert "/api/leads/export" not in schema["paths"]


@pytest.mark.integration
async def test_search_schema_has_no_legacy_controls_or_contacts() -> None:
    app, _ = integration_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        schema = (await client.get("/openapi.json")).json()

    request_properties = schema["components"]["schemas"]["GooglePlaceSearchRequest"]["properties"]
    place_properties = schema["components"]["schemas"]["GooglePlaceSummary"]["properties"]
    assert {"target", "max_tiles", "max_pages", "contact_fields"}.isdisjoint(request_properties)
    assert {"phone", "international_phone", "website"}.isdisjoint(place_properties)


@pytest.mark.integration
async def test_search_rejects_missing_google_configuration_before_provider_call() -> None:
    identity = authenticated_identity()
    settings = Settings(cors_allowed_origins=("http://test",))
    app = create_app(settings)
    app.state.container = AppContainer(
        settings=settings,
        search_google_places=app.state.container.search_google_places,
        get_map_snapshot=app.state.container.get_map_snapshot,
        get_current_session=CurrentSession({SESSION_TOKEN: identity}),  # type: ignore[arg-type]
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/google/places/search",
            json=search_payload(),
            headers=authorize(client),
        )

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["error"]["code"] == "google_not_configured"


@pytest.mark.integration
async def test_google_routes_require_a_session_before_any_provider_call() -> None:
    maps = FakeStaticMapGateway()
    app, places = integration_app(map_gateway=maps)
    headers = {"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        search = await client.post("/api/google/places/search", json=search_payload(), headers=headers)
        snapshot = await client.post("/api/map/snapshot", json={"token": "x" * 32}, headers=headers)

    assert search.status_code == snapshot.status_code == 401
    assert search.json()["error"]["code"] == "authentication_required"
    assert snapshot.json()["error"]["code"] == "authentication_required"
    assert places.calls == maps.calls == 0


@pytest.mark.integration
@pytest.mark.parametrize("platform", [False, True])
async def test_google_search_requires_an_active_organization_even_for_platform_admin(platform: bool) -> None:
    identity = identity_without_organization(platform=platform)
    app, places = integration_app(identities={SESSION_TOKEN: identity})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/google/places/search",
            json=search_payload(),
            headers=authorize(client),
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "active_organization_required"
    assert places.calls == 0


@pytest.mark.integration
async def test_google_search_requires_trusted_origin_and_csrf() -> None:
    app, places = integration_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        missing_origin = await client.post(
            "/api/google/places/search",
            json=search_payload(),
            headers={"X-CSRF-Token": CSRF_TOKEN},
        )
        missing_csrf = await client.post(
            "/api/google/places/search",
            json=search_payload(),
            headers={"Origin": "http://test"},
        )
        invalid_csrf = await client.post(
            "/api/google/places/search",
            json=search_payload(),
            headers={"Origin": "http://test", "X-CSRF-Token": "wrong"},
        )

    assert {missing_origin.status_code, missing_csrf.status_code, invalid_csrf.status_code} == {403}
    assert places.calls == 0


@pytest.mark.integration
async def test_google_search_rejects_client_identity_tenant_and_non_json_payloads() -> None:
    app, places = integration_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = authorize(client)
        requester = await client.post(
            "/api/google/places/search",
            json={**search_payload(), "requester": {"first_name": "Anne"}},
            headers=headers,
        )
        tenant = await client.post(
            "/api/google/places/search",
            json={**search_payload(), "organization_id": str(uuid4())},
            headers=headers,
        )
        non_json = await client.post(
            "/api/google/places/search",
            content="query=plombier",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
        )

    assert requester.status_code == tenant.status_code == 422
    assert non_json.status_code == 415
    assert all(response.headers["cache-control"] == "no-store, max-age=0" for response in (requester, tenant, non_json))
    assert places.calls == 0


@pytest.mark.integration
@pytest.mark.parametrize("role", list(MembershipRole))
async def test_active_tenant_roles_can_search_and_fetch_a_map(role: MembershipRole) -> None:
    identity = authenticated_identity(role=role)
    app, _ = integration_app(identities={SESSION_TOKEN: identity})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = authorize(client)
        search = await client.post("/api/google/places/search", json=search_payload(), headers=headers)
        snapshot = await client.post(
            "/api/map/snapshot",
            json={"token": search.json()["map_snapshot_token"]},
            headers=headers,
        )

    assert search.status_code == snapshot.status_code == 200


@pytest.mark.integration
async def test_capabilities_are_checked_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    maps = FakeStaticMapGateway()
    app, places = integration_app(map_gateway=maps)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = authorize(client)
        monkeypatch.setitem(CAPABILITIES_BY_ROLE, MembershipRole.SALES, ("organization:read",))
        denied_search = await client.post("/api/google/places/search", json=search_payload(), headers=headers)

        monkeypatch.setitem(
            CAPABILITIES_BY_ROLE,
            MembershipRole.SALES,
            ("organization:read", "google:search"),
        )
        allowed_search = await client.post("/api/google/places/search", json=search_payload(), headers=headers)
        denied_map = await client.post(
            "/api/map/snapshot",
            json={"token": allowed_search.json()["map_snapshot_token"]},
            headers=headers,
        )

    assert denied_search.status_code == denied_map.status_code == 403
    assert denied_search.json()["error"]["code"] == "insufficient_capability"
    assert denied_map.json()["error"]["code"] == "insufficient_capability"
    assert places.calls == 1
    assert maps.calls == 0


@pytest.mark.integration
@pytest.mark.parametrize("same_organization", [True, False])
async def test_map_grant_cannot_be_stolen_and_remains_available_to_owner(same_organization: bool) -> None:
    owner = authenticated_identity()
    owner_membership = owner.active_membership
    assert owner_membership is not None
    intruder = authenticated_identity(
        organization_id=owner_membership.organization_id if same_organization else uuid4(),
    )
    app, _ = integration_app(identities={"owner": owner, "intruder": intruder})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner_headers = authorize(client, "owner")
        search = await client.post("/api/google/places/search", json=search_payload(), headers=owner_headers)
        token = search.json()["map_snapshot_token"]

        intruder_headers = authorize(client, "intruder")
        stolen = await client.post("/api/map/snapshot", json={"token": token}, headers=intruder_headers)

        owner_headers = authorize(client, "owner")
        legitimate = await client.post("/api/map/snapshot", json={"token": token}, headers=owner_headers)

    assert stolen.status_code == 403
    assert stolen.json()["error"]["code"] == "invalid_map_grant"
    assert legitimate.status_code == 200


@pytest.mark.integration
async def test_map_provider_failure_is_terminal_and_does_not_leak_details() -> None:
    maps = FakeStaticMapGateway(fail=True)
    app, _ = integration_app(map_gateway=maps)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = authorize(client)
        search = await client.post("/api/google/places/search", json=search_payload(), headers=headers)
        token = search.json()["map_snapshot_token"]
        failed = await client.post("/api/map/snapshot", json={"token": token}, headers=headers)
        replay = await client.post("/api/map/snapshot", json={"token": token}, headers=headers)

    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "google_map_unavailable"
    assert failed.json()["error"]["request_id"]
    assert "provider-secret" not in failed.text
    assert replay.status_code == 403
    assert maps.calls == 1


@pytest.mark.integration
async def test_concurrent_searches_for_same_actor_reach_provider_once() -> None:
    places = BlockingPlacesGateway()
    app, _ = integration_app(places_gateway=places)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = authorize(client)
        first_task = asyncio.create_task(
            client.post("/api/google/places/search", json=search_payload(), headers=headers)
        )
        await places.started.wait()
        second = await client.post("/api/google/places/search", json=search_payload(), headers=headers)
        places.release.set()
        first = await first_task

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "google_search_in_progress"
    assert places.calls == 1
