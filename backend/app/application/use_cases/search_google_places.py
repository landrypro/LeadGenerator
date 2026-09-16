from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from uuid import UUID, uuid4

from ...domain.geo import haversine_km
from ...domain.google_place import GooglePlaceSearchResult, GooglePlaceSearchStats, GooglePlaceSummary
from ..errors import GoogleProtectionUnavailable, GoogleQuotaExceeded, GoogleSearchInProgress, PlacesProviderError
from ..models import GoogleAccessContext, GooglePlaceSearchCriteria, MapPoint, MapSnapshot
from ..ports.clock import Clock
from ..ports.generation_guard import GenerationGuard
from ..ports.google_quota import GoogleSearchPolicyProvider, GoogleSearchQuota
from ..ports.map_grants import MapSnapshotGrantStore
from ..ports.metrics import MetricsRecorder, NullMetricsRecorder
from ..ports.places import PlaceCandidate, PlacesGateway
from ..ports.prospect import GoogleSelectionGrantStore

MAX_GOOGLE_RESULTS = 20


@dataclass(frozen=True, slots=True)
class SearchGooglePlacesOutcome:
    search: GooglePlaceSearchResult
    map_snapshot_token: str
    selection_token: str


class SearchGooglePlacesUseCase:
    """Exécute une unique recherche Text Search et garde ses résultats éphémères."""

    def __init__(
        self,
        places: PlacesGateway,
        generation_guard: GenerationGuard,
        map_grants: MapSnapshotGrantStore,
        selection_grants: GoogleSelectionGrantStore,
        policy_provider: GoogleSearchPolicyProvider,
        quota: GoogleSearchQuota,
        clock: Clock,
        operation_id_factory: Callable[[], UUID] = uuid4,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._places = places
        self._generation_guard = generation_guard
        self._map_grants = map_grants
        self._selection_grants = selection_grants
        self._policy_provider = policy_provider
        self._quota = quota
        self._clock = clock
        self._operation_id_factory = operation_id_factory
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(
        self,
        criteria: GooglePlaceSearchCriteria,
        access: GoogleAccessContext,
    ) -> SearchGooglePlacesOutcome:
        policy = await self._policy_provider.resolve(access.owner)
        try:
            async with self._generation_guard.hold(access.owner):
                self._metrics.record_google_search_lock("accepted")
                reservation = await self._quota.reserve(
                    access.owner,
                    policy,
                    self._operation_id_factory(),
                    now=self._clock.now(),
                )
                if not reservation.allowed:
                    self._metrics.record_google_search_quota(
                        reservation.scope or "user", "rejected", policy.policy_code
                    )
                    raise GoogleQuotaExceeded(reservation.scope or "user", reservation.retry_after_seconds)
                self._metrics.record_google_search_quota("user", "accepted", policy.policy_code)
                self._metrics.record_google_search_quota("organization", "accepted", policy.policy_code)
                candidates = await self._search_places(criteria)
        except GoogleSearchInProgress:
            self._metrics.record_google_search_lock("contended")
            raise
        except GoogleProtectionUnavailable:
            self._metrics.record_google_search_lock("unavailable")
            raise
        else:
            search = self._build_result(candidates, criteria, searched_at=self._clock.now())
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
            selection_token = await self._selection_grants.issue(
                tuple(place.place_id for place in search.places),
                access.owner,
                now=search.searched_at,
            )
            return SearchGooglePlacesOutcome(
                search=search,
                map_snapshot_token=token,
                selection_token=selection_token,
            )

    async def _search_places(self, criteria: GooglePlaceSearchCriteria):  # type: ignore[no-untyped-def]
        started_at = perf_counter()
        try:
            candidates = await self._places.search(criteria)
        except PlacesProviderError:
            self._metrics.record_google_upstream("places_text_search", "failed", perf_counter() - started_at)
            raise
        self._metrics.record_google_upstream("places_text_search", "accepted", perf_counter() - started_at)
        return candidates

    @staticmethod
    def _build_result(
        candidates: list[PlaceCandidate],
        criteria: GooglePlaceSearchCriteria,
        *,
        searched_at: datetime,
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
            searched_at=searched_at,
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
