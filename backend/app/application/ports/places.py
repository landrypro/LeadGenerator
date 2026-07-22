from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.geo import SearchTile
from ..models import SearchCriteria


@dataclass(frozen=True, slots=True)
class PlaceCandidate:
    place_id: str = ""
    name: str = ""
    address: str = ""
    phone: str = ""
    international_phone: str = ""
    website: str = ""
    google_maps_url: str = ""
    latitude: float | None = None
    longitude: float | None = None
    primary_type: str = ""
    business_status: str = ""
    service_area_business: bool = False


@dataclass(frozen=True, slots=True)
class PlaceSearchPage:
    places: list[PlaceCandidate]
    next_page_token: str | None


class PlacesGateway(Protocol):
    async def search_page(
        self,
        criteria: SearchCriteria,
        tile: SearchTile,
        page_token: str | None = None,
    ) -> PlaceSearchPage: ...
