from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.application.use_cases.generate_leads import GenerateLeadsResult
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.lead import SearchResult, SearchStats


class StubGenerateLeads:
    def __init__(self) -> None:
        self.criteria = None
        self.business_address = None

    async def execute(self, criteria, business_address):
        self.criteria = criteria
        self.business_address = business_address
        return GenerateLeadsResult(
            search=SearchResult(
                leads=[],
                stats=SearchStats(),
                generated_at=datetime.now(timezone.utc),
            ),
            map_snapshot_token="injected-token",
        )


def test_create_app_uses_injected_settings_for_health() -> None:
    app = create_app(Settings(google_maps_api_key="configured"))

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "google_api_key_configured": True}


def test_routes_receive_injected_use_cases() -> None:
    settings = Settings(google_maps_api_key="fake-key")
    generate_leads = StubGenerateLeads()
    container = AppContainer(
        settings=settings,
        generate_leads=generate_leads,
        export_leads=object(),
        get_map_snapshot=object(),
    )
    app = create_app(container=container)

    with TestClient(app) as client:
        response = client.post(
            "/api/leads/search",
            json={
                "query": "plombier",
                "center_latitude": 46.8,
                "center_longitude": -71.2,
                "radius_km": 12,
                "target": 25,
                "max_tiles": 2,
                "max_pages": 1,
                "requester": {
                    "first_name": "Anne",
                    "company_name": "Exemple Inc.",
                    "business_address": "100 rue Principale, Québec",
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["map_snapshot_token"] == "injected-token"
    assert response.json()["search_parameters"]["radius_km"] == 12
    assert generate_leads.criteria.target == 25
    assert generate_leads.business_address == "100 rue Principale, Québec"
