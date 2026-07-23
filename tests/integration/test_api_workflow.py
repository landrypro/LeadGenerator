import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.application.models import GooglePlaceSearchCriteria
from backend.app.application.ports.maps import MapImage
from backend.app.application.ports.places import PlaceCandidate
from backend.app.application.use_cases import GetMapSnapshotUseCase, SearchGooglePlacesUseCase
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.infrastructure.memory import InMemoryGenerationGuard, InMemoryMapSnapshotGrantStore


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
    async def fetch(self, payload: object) -> MapImage:
        return MapImage(content=b"fake-png", media_type="image/png")


def integration_app() -> tuple[object, FakePlacesGateway]:
    settings = Settings(
        google_maps_api_key="test-places-key",
        google_maps_static_api_key="test-static-key",
    )
    places = FakePlacesGateway()
    grants = InMemoryMapSnapshotGrantStore()
    container = AppContainer(
        settings=settings,
        search_google_places=SearchGooglePlacesUseCase(
            places,
            InMemoryGenerationGuard(),
            grants,
        ),
        get_map_snapshot=GetMapSnapshotUseCase(grants, FakeStaticMapGateway()),
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
        "requester": {
            "first_name": "Anne",
            "company_name": "Exemple Inc.",
            "business_address": "200 rue du Test, Québec",
        },
    }


@pytest.mark.integration
async def test_limited_search_and_protected_map_workflow_through_http() -> None:
    app, places_gateway = integration_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        search_response = await client.post("/api/google/places/search", json=search_payload())

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
        map_response = await client.post("/api/map/snapshot", json={"token": token})
        assert map_response.status_code == 200
        assert map_response.content == b"fake-png"
        assert map_response.headers["cache-control"] == "no-store, max-age=0"

        replay_response = await client.post("/api/map/snapshot", json={"token": token})
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
    app = create_app(Settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/google/places/search", json=search_payload())

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["detail"].startswith("GOOGLE_MAPS_API_KEY")
