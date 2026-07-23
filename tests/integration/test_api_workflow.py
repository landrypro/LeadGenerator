import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.application.ports.maps import MapImage
from backend.app.application.ports.places import PlaceCandidate, PlaceSearchPage
from backend.app.application.use_cases import (
    ExportLeadsUseCase,
    GenerateLeadsUseCase,
    GetMapSnapshotUseCase,
    SearchLeadsUseCase,
)
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.infrastructure.export.excel import ExcelLeadExporter
from backend.app.infrastructure.memory import InMemoryGenerationGuard, InMemoryMapSnapshotGrantStore


class FakePlacesGateway:
    async def search_page(self, criteria, tile, page_token=None):
        return PlaceSearchPage(
            places=[
                PlaceCandidate(
                    place_id="place-integration-1",
                    name="Plomberie Boréale",
                    address="100 rue Principale, Québec",
                    phone="418-555-0100" if criteria.contact_fields else "",
                    google_maps_url="https://maps.google.com/?cid=test",
                    latitude=46.8139,
                    longitude=-71.2080,
                    primary_type="plumber",
                    business_status="OPERATIONAL",
                )
            ],
            next_page_token=None,
        )


class FakeStaticMapGateway:
    async def fetch(self, payload):
        assert payload.points
        return MapImage(content=b"fake-png", media_type="image/png")


def integration_app():
    settings = Settings(
        google_maps_api_key="test-places-key",
        google_maps_static_api_key="test-static-key",
    )
    grants = InMemoryMapSnapshotGrantStore()
    container = AppContainer(
        settings=settings,
        generate_leads=GenerateLeadsUseCase(
            SearchLeadsUseCase(FakePlacesGateway()),
            InMemoryGenerationGuard(),
            grants,
        ),
        export_leads=ExportLeadsUseCase(ExcelLeadExporter()),
        get_map_snapshot=GetMapSnapshotUseCase(grants, FakeStaticMapGateway()),
    )
    return create_app(container=container)


def search_payload():
    return {
        "query": "plombier",
        "center_latitude": 46.8139,
        "center_longitude": -71.2080,
        "radius_km": 10,
        "target": 20,
        "max_tiles": 1,
        "max_pages": 1,
        "contact_fields": True,
        "requester": {
            "first_name": "Anne",
            "company_name": "Exemple Inc.",
            "business_address": "200 rue du Test, Québec",
        },
    }


@pytest.mark.integration
async def test_search_map_and_export_workflow_through_http() -> None:
    app = integration_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        search_response = await client.post("/api/leads/search", json=search_payload())

        assert search_response.status_code == 200
        body = search_response.json()
        assert body["leads"][0]["place_id"] == "place-integration-1"
        assert body["leads"][0]["phone"] == "418-555-0100"
        assert body["search_parameters"]["radius_km"] == 10

        token = body["map_snapshot_token"]
        map_response = await client.post("/api/map/snapshot", json={"token": token})
        assert map_response.status_code == 200
        assert map_response.content == b"fake-png"
        assert map_response.headers["cache-control"] == "no-store, max-age=0"

        replay_response = await client.post("/api/map/snapshot", json={"token": token})
        assert replay_response.status_code == 403

        export_response = await client.post(
            "/api/leads/export",
            json={"leads": body["leads"], "search": body["search_parameters"]},
        )
        assert export_response.status_code == 200
        assert export_response.content.startswith(b"PK")
        assert export_response.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


@pytest.mark.integration
async def test_search_rejects_missing_google_configuration_before_calling_provider() -> None:
    app = create_app(Settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/leads/search", json=search_payload())

    assert response.status_code == 503
    assert response.json()["detail"].startswith("GOOGLE_MAPS_API_KEY")


@pytest.mark.integration
async def test_legacy_search_and_export_remain_marked_as_deprecated() -> None:
    app = integration_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        schema = (await client.get("/openapi.json")).json()

    assert schema["paths"]["/api/leads/search"]["post"]["deprecated"] is True
    assert schema["paths"]["/api/leads/export"]["post"]["deprecated"] is True
    search_properties = schema["components"]["schemas"]["LeadGenerationRequest"]["properties"]
    assert search_properties["target"]["deprecated"] is True
    assert search_properties["max_tiles"]["deprecated"] is True
    assert search_properties["max_pages"]["deprecated"] is True
