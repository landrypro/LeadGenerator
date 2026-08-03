from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GoogleAccessOwner:
    user_id: UUID
    organization_id: UUID


@dataclass(frozen=True, slots=True)
class GoogleAccessContext:
    user_id: UUID
    organization_id: UUID
    membership_id: UUID

    @property
    def owner(self) -> GoogleAccessOwner:
        return GoogleAccessOwner(self.user_id, self.organization_id)


@dataclass(frozen=True, slots=True)
class GooglePlaceSearchCriteria:
    query: str
    center_latitude: float = 46.8139
    center_longitude: float = -71.2080
    radius_km: float = 15
    include_service_area_businesses: bool = True
    language_code: str = "fr"
    region_code: str = "CA"


@dataclass(frozen=True, slots=True)
class MapPoint:
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class MapSnapshot:
    center_latitude: float
    center_longitude: float
    radius_km: float
    points: list[MapPoint] = field(default_factory=list)
