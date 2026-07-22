from __future__ import annotations

from dataclasses import dataclass

from ...domain.lead import SearchResult
from ..models import MapPoint, MapSnapshot, SearchCriteria
from ..ports.generation_guard import GenerationGuard
from ..ports.map_grants import MapSnapshotGrantStore
from .search_leads import SearchLeadsUseCase


@dataclass(frozen=True, slots=True)
class GenerateLeadsResult:
    search: SearchResult
    map_snapshot_token: str


class GenerateLeadsUseCase:
    def __init__(
        self,
        search_leads: SearchLeadsUseCase,
        generation_guard: GenerationGuard,
        map_grants: MapSnapshotGrantStore,
    ) -> None:
        self._search_leads = search_leads
        self._generation_guard = generation_guard
        self._map_grants = map_grants

    async def execute(self, criteria: SearchCriteria, business_address: str) -> GenerateLeadsResult:
        async with self._generation_guard.hold(business_address):
            result = await self._search_leads.execute(criteria)
            snapshot = MapSnapshot(
                center_latitude=criteria.center_latitude,
                center_longitude=criteria.center_longitude,
                radius_km=criteria.radius_km,
                points=[
                    MapPoint(latitude=lead.latitude, longitude=lead.longitude)
                    for lead in result.leads
                    if lead.latitude is not None and lead.longitude is not None
                ][:50],
            )
            token = await self._map_grants.issue(snapshot)
            return GenerateLeadsResult(search=result, map_snapshot_token=token)
