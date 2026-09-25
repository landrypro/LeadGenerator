from dataclasses import fields
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.application.models import (
    GoogleAccessContext,
    GoogleAccessOwner,
    GooglePlaceSearchCriteria,
    GoogleQuotaReservation,
    GoogleSearchQuotaPolicy,
)
from backend.app.application.ports.places import PlaceCandidate
from backend.app.application.ports.usage import UsageEvent
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


class PermissiveGoogleSearchPolicy:
    async def resolve(self, owner: GoogleAccessOwner) -> GoogleSearchQuotaPolicy:
        del owner
        return GoogleSearchQuotaPolicy(True, 20, 100, 80, "test_policy")


class PermissiveGoogleSearchQuota:
    async def reserve(
        self,
        owner: GoogleAccessOwner,
        policy: GoogleSearchQuotaPolicy,
        operation_id: object,
        *,
        now: datetime,
    ) -> GoogleQuotaReservation:
        del owner, operation_id
        return GoogleQuotaReservation(
            True,
            None,
            1,
            policy.user_daily_limit - 1,
            1,
            policy.organization_daily_limit - 1,
            now,
            1,
            policy.policy_code,
        )


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 25, 12, tzinfo=UTC)


class UsageRecorder:
    def __init__(self) -> None:
        self.events: list[UsageEvent] = []

    async def record(self, event: UsageEvent) -> None:
        self.events.append(event)


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
        PermissiveGoogleSearchPolicy(),
        PermissiveGoogleSearchQuota(),
        FixedClock(),
    )


def tracked_use_case(gateway: FakePlacesGateway, usage: UsageRecorder) -> SearchGooglePlacesUseCase:
    return SearchGooglePlacesUseCase(
        gateway,
        InMemoryGenerationGuard(),
        InMemoryMapSnapshotGrantStore(),
        InMemoryGoogleSelectionGrantStore(),
        PermissiveGoogleSearchPolicy(),
        PermissiveGoogleSearchQuota(),
        FixedClock(),
        usage=usage,  # type: ignore[arg-type]
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
async def test_use_case_records_reservation_attempt_and_success_with_one_operation() -> None:
    gateway = FakePlacesGateway([candidate(1)])
    usage = UsageRecorder()

    await tracked_use_case(gateway, usage).execute(GooglePlaceSearchCriteria(query="plombier"), access_context())

    assert [event.event_kind for event in usage.events] == [
        "quota_reserved",
        "upstream_attempted",
        "upstream_succeeded",
    ]
    assert len({event.operation_id for event in usage.events}) == 1
    assert all(event.context.organization_id == usage.events[0].context.organization_id for event in usage.events)


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
