from datetime import UTC, datetime

from backend.app.application.use_cases.search_google_places import SearchGooglePlacesOutcome
from backend.app.domain.google_place import GooglePlaceSearchResult, GooglePlaceSearchStats
from backend.app.presentation.api.mappers import to_search_response
from backend.app.presentation.api.schemas import GooglePlaceSearchRequest


def test_search_response_preserves_effective_parameters_without_requester() -> None:
    request = GooglePlaceSearchRequest.model_validate(
        {
            "query": " électricien  commercial ",
            "center_latitude": 45.5019,
            "center_longitude": -73.5674,
            "radius_km": 12,
        }
    )
    outcome = SearchGooglePlacesOutcome(
        search=GooglePlaceSearchResult(
            searched_at=datetime.now(UTC),
            stats=GooglePlaceSearchStats(api_calls=1, raw_results=0, displayed_results=0),
        ),
        map_snapshot_token="snapshot-token",
    )

    serialized = to_search_response(outcome, request).model_dump(mode="json")

    assert serialized["search_parameters"]["query"] == "électricien commercial"
    assert serialized["search_parameters"]["radius_km"] == 12
    assert "requester" not in serialized["search_parameters"]
    assert "target" not in serialized["search_parameters"]
    assert "max_tiles" not in serialized["search_parameters"]
    assert "max_pages" not in serialized["search_parameters"]
