from dataclasses import fields
from uuid import uuid4

import pytest

from backend.app.application.models import GoogleAccessContext, GooglePlaceSearchCriteria
from backend.app.application.ports.places import PlaceCandidate
from backend.app.application.use_cases.search_google_places import (
    MAX_GOOGLE_RESULTS,
    SearchGooglePlacesUseCase,
)
from backend.app.infrastructure.memory import (
    InMemoryGenerationGuard,
    InMemoryGoogleSelectionGrantStore,
    InMemoryMapSnapshotGrantStore,
)


class FakePlacesGateway:
    def __init__(self, candidates: list[PlaceCandidate]) -> None:
        self.candidates = candidates
        self.calls = 0

    async def search(self, criteria: GooglePlaceSearchCriteria) -> list[PlaceCandidate]:
        self.calls += 1
        return self.candidates


def candidate(index: int, **overrides: object) -> PlaceCandidate:
    values: dict[str, object] = {
        "place_id": f"place-{index}",
        "name": f"Entreprise {index}",
        "address": "Québec",
        "latitude": 46.8139,
        "longitude": -71.2080,
    }
    values.update(overrides)
    return PlaceCandidate(**values)  # type: ignore[arg-type]


def use_case(gateway: FakePlacesGateway) -> SearchGooglePlacesUseCase:
    return SearchGooglePlacesUseCase(
        gateway,
        InMemoryGenerationGuard(),
        InMemoryMapSnapshotGrantStore(),
        InMemoryGoogleSelectionGrantStore(),
    )


def access_context() -> GoogleAccessContext:
    return GoogleAccessContext(uuid4(), uuid4(), uuid4())


@pytest.mark.asyncio
async def test_use_case_calls_gateway_once_and_limits_results_to_twenty() -> None:
    gateway = FakePlacesGateway([candidate(index) for index in range(25)])

    outcome = await use_case(gateway).execute(
        GooglePlaceSearchCriteria(query="plombier"),
        access_context(),
    )

    assert gateway.calls == 1
    assert len(outcome.search.places) == MAX_GOOGLE_RESULTS == 20
    assert outcome.search.stats.api_calls == 1
    assert outcome.search.stats.raw_results == 25
    assert outcome.selection_token


@pytest.mark.asyncio
async def test_use_case_deduplicates_and_filters_outside_radius() -> None:
    gateway = FakePlacesGateway(
        [
            candidate(1),
            candidate(2, place_id="place-1"),
            candidate(3, latitude=45.5019, longitude=-73.5674),
        ]
    )

    outcome = await use_case(gateway).execute(
        GooglePlaceSearchCriteria(query="plombier", radius_km=10),
        access_context(),
    )

    assert [place.place_id for place in outcome.search.places] == ["place-1"]
    assert outcome.search.stats.duplicates_removed == 1
    assert outcome.search.stats.outside_radius_removed == 1


def test_place_candidate_has_no_contact_fields() -> None:
    names = {field.name for field in fields(PlaceCandidate)}

    assert names.isdisjoint({"phone", "international_phone", "website"})
