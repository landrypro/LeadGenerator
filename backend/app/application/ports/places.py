from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import GooglePlaceSearchCriteria


@dataclass(frozen=True, slots=True)
class PlaceCandidate:
    place_id: str = ""
    name: str = ""
    address: str = ""
    google_maps_url: str = ""
    latitude: float | None = None
    longitude: float | None = None
    primary_type: str = ""
    business_status: str = ""
    service_area_business: bool = False


class PlacesGateway(Protocol):
    async def search(self, criteria: GooglePlaceSearchCriteria) -> list[PlaceCandidate]: ...
