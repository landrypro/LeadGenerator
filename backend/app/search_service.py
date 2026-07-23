"""Façade compatible de l’ancien service, adossée au nouveau cas d’utilisation."""

from __future__ import annotations

from typing import Protocol

from .application.models import SearchCriteria
from .application.ports.places import PlaceCandidate, PlaceSearchPage
from .application.use_cases.search_leads import SearchLeadsUseCase
from .domain.geo import SearchTile
from .infrastructure.google.places import PlacesPage, google_place_to_candidate
from .presentation.api.schemas import Lead, SearchRequest, SearchResponse, SearchStats


class PlacesClient(Protocol):
    async def search_page(
        self,
        request: SearchCriteria,
        tile: SearchTile,
        page_token: str | None = None,
    ) -> PlacesPage: ...


class _LegacyPlacesGateway:
    def __init__(self, client: PlacesClient) -> None:
        self._client = client

    async def search_page(
        self,
        criteria: SearchCriteria,
        tile: SearchTile,
        page_token: str | None = None,
    ) -> PlaceSearchPage:
        page = await self._client.search_page(criteria, tile, page_token)
        candidates = [
            place if isinstance(place, PlaceCandidate) else google_place_to_candidate(place) for place in page.places
        ]
        return PlaceSearchPage(candidates, page.next_page_token)


class LeadSearchService:
    def __init__(self, client: PlacesClient) -> None:
        self._use_case = SearchLeadsUseCase(_LegacyPlacesGateway(client))

    async def search(self, request: SearchRequest) -> SearchResponse:
        criteria = SearchCriteria(**request.model_dump())
        result = await self._use_case.execute(criteria)
        return SearchResponse(
            leads=[Lead.model_validate(lead, from_attributes=True) for lead in result.leads],
            stats=SearchStats.model_validate(result.stats, from_attributes=True),
            generated_at=result.generated_at,
        )


__all__ = ["LeadSearchService", "PlacesClient"]
