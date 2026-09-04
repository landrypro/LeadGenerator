from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.use_cases.search_google_places import SearchGooglePlacesOutcome
from backend.app.bootstrap import build_container, create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.google_place import GooglePlaceSearchResult, GooglePlaceSearchStats
from backend.app.domain.identity import (
    AuthenticatedIdentity,
    MembershipIdentity,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    UserIdentity,
    UserStatus,
)


class StubSearchGooglePlaces:
    def __init__(self) -> None:
        self.criteria = None
        self.access = None

    async def execute(self, criteria: object, access: object) -> SearchGooglePlacesOutcome:
        self.criteria = criteria
        self.access = access
        return SearchGooglePlacesOutcome(
            search=GooglePlaceSearchResult(
                places=[],
                stats=GooglePlaceSearchStats(api_calls=1, raw_results=0, displayed_results=0),
                searched_at=datetime.now(UTC),
            ),
            map_snapshot_token="injected-token",
            selection_token="selection-token",
        )


def authenticated_identity() -> AuthenticatedIdentity:
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=uuid4(),
        organization_name="Entreprise Exemple",
        role=MembershipRole.SALES,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=datetime.now(UTC),
    )
    user = UserIdentity(
        id=uuid4(),
        email="anne@example.ca",
        display_name="Anne",
        password_hash="not-serialized",
        status=UserStatus.ACTIVE,
        platform_role=None,
        last_active_organization_id=membership.organization_id,
        version=1,
        memberships=(membership,),
    )
    return AuthenticatedIdentity(user, membership, "csrf-test")


class CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "current-session"
        return self.identity


async def test_create_app_uses_injected_settings_for_health() -> None:
    app = create_app(Settings(google_maps_api_key="configured"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "google_api_key_configured": True}


async def test_default_container_without_redis_fails_google_closed_without_memory_fallback() -> None:
    settings = Settings(google_maps_api_key="configured", cors_allowed_origins=("http://test",))
    default_container = build_container(settings)
    identity = authenticated_identity()
    container = AppContainer(
        settings=settings,
        search_google_places=default_container.search_google_places,
        get_map_snapshot=default_container.get_map_snapshot,
        get_current_session=CurrentSession(identity),  # type: ignore[arg-type]
    )
    app = create_app(container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set(settings.session_cookie_name, "current-session")
        response = await client.post(
            "/api/google/places/search",
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-test"},
            json={
                "query": "plombier",
                "center_latitude": 46.8,
                "center_longitude": -71.2,
                "radius_km": 12,
            },
        )

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["error"]["code"] == "google_protection_unavailable"


async def test_routes_receive_injected_use_cases() -> None:
    settings = Settings(google_maps_api_key="fake-key", cors_allowed_origins=("http://test",))
    search_google_places = StubSearchGooglePlaces()
    identity = authenticated_identity()
    container = AppContainer(
        settings=settings,
        search_google_places=search_google_places,  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=CurrentSession(identity),  # type: ignore[arg-type]
    )
    app = create_app(container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set(settings.session_cookie_name, "current-session")
        response = await client.post(
            "/api/google/places/search",
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-test"},
            json={
                "query": "plombier",
                "center_latitude": 46.8,
                "center_longitude": -71.2,
                "radius_km": 12,
            },
        )

    assert response.status_code == 200
    assert response.json()["map_snapshot_token"] == "injected-token"
    assert response.json()["selection_token"] == "selection-token"
    assert response.json()["search_parameters"]["radius_km"] == 12
    assert search_google_places.access.user_id == identity.user.id
    assert search_google_places.access.organization_id == identity.active_membership.organization_id
