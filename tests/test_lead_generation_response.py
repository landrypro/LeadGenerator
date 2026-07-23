from datetime import UTC, datetime

from backend.app.models import LeadGenerationResponse, SearchRequest, SearchStats


def test_generation_response_preserves_effective_search_parameters() -> None:
    parameters = SearchRequest(
        query="électricien",
        center_latitude=45.5019,
        center_longitude=-73.5674,
        radius_km=12,
        target=75,
        max_tiles=4,
        max_pages=2,
        contact_fields=True,
    )

    response = LeadGenerationResponse(
        leads=[],
        stats=SearchStats(),
        generated_at=datetime.now(UTC),
        map_snapshot_token="snapshot-token",
        search_parameters=parameters,
    )

    serialized = response.model_dump(mode="json")

    assert serialized["search_parameters"] == parameters.model_dump(mode="json")
    assert "requester" not in serialized["search_parameters"]
