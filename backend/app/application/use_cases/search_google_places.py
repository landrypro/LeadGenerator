from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ...domain.geo import haversine_km
from ...domain.google_place import GooglePlaceSearchResult, GooglePlaceSearchStats, GooglePlaceSummary
from ..models import GoogleAccessContext, GooglePlaceSearchCriteria, MapPoint, MapSnapshot
from ..ports.generation_guard import GenerationGuard
from ..ports.map_grants import MapSnapshotGrantStore
from ..ports.places import PlaceCandidate, PlacesGateway

MAX_GOOGLE_RESULTS = 20


@dataclass(frozen=True, slots=True)
class SearchGooglePlacesOutcome:
    search: GooglePlaceSearchResult
    map_snapshot_token: str


class SearchGooglePlacesUseCase:
    """Exécute une unique recherche Text Search et garde ses résultats éphémères."""

    def __init__(
        self,
        places: PlacesGateway,
        generation_guard: GenerationGuard,
        map_grants: MapSnapshotGrantStore,
    ) -> None:
        self._places = places
        self._generation_guard = generation_guard
        self._map_grants = map_grants

    async def execute(
        self,
        criteria: GooglePlaceSearchCriteria,
        access: GoogleAccessContext,
    ) -> SearchGooglePlacesOutcome:
        async with self._generation_guard.hold(access.owner):
            candidates = await self._places.search(criteria)
            search = self._build_result(candidates, criteria)
            snapshot = MapSnapshot(
                center_latitude=criteria.center_latitude,
                center_longitude=criteria.center_longitude,
                radius_km=criteria.radius_km,
                points=[
                    MapPoint(latitude=place.latitude, longitude=place.longitude)
                    for place in search.places
                    if place.latitude is not None and place.longitude is not None
                ],
            )
            token = await self._map_grants.issue(snapshot, access.owner)
            return SearchGooglePlacesOutcome(search=search, map_snapshot_token=token)

    @staticmethod
    def _build_result(
        candidates: list[PlaceCandidate],
        criteria: GooglePlaceSearchCriteria,
    ) -> GooglePlaceSearchResult:
        places: list[GooglePlaceSummary] = []
        seen_place_ids: set[str] = set()
        duplicates_removed = 0
        outside_radius_removed = 0
        service_area_unverified = 0

        for candidate in candidates:
            if len(places) >= MAX_GOOGLE_RESULTS:
                break
            if candidate.place_id and candidate.place_id in seen_place_ids:
                duplicates_removed += 1
                continue

            place = SearchGooglePlacesUseCase._to_summary(candidate, criteria)
            if not place.radius_verified:
                if not criteria.include_service_area_businesses:
                    outside_radius_removed += 1
                    continue
                service_area_unverified += 1
            elif place.distance_km is not None and place.distance_km > criteria.radius_km:
                outside_radius_removed += 1
                continue

            if candidate.place_id:
                seen_place_ids.add(candidate.place_id)
            places.append(place)

        return GooglePlaceSearchResult(
            places=places,
            stats=GooglePlaceSearchStats(
                api_calls=1,
                raw_results=len(candidates),
                displayed_results=len(places),
                duplicates_removed=duplicates_removed,
                outside_radius_removed=outside_radius_removed,
                service_area_unverified=service_area_unverified,
            ),
            searched_at=datetime.now(UTC),
        )

    @staticmethod
    def _to_summary(
        candidate: PlaceCandidate,
        criteria: GooglePlaceSearchCriteria,
    ) -> GooglePlaceSummary:
        if candidate.latitude is None or candidate.longitude is None:
            distance = None
        else:
            distance = round(
                haversine_km(
                    criteria.center_latitude,
                    criteria.center_longitude,
                    candidate.latitude,
                    candidate.longitude,
                ),
                3,
            )
        return GooglePlaceSummary(
            place_id=candidate.place_id,
            name=candidate.name,
            address=candidate.address,
            google_maps_url=candidate.google_maps_url,
            latitude=candidate.latitude,
            longitude=candidate.longitude,
            primary_type=candidate.primary_type,
            business_status=candidate.business_status,
            service_area_business=candidate.service_area_business,
            distance_km=distance,
            radius_verified=distance is not None,
        )
