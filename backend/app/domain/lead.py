from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Lead:
    name: str = ""
    address: str = ""
    phone: str = ""
    international_phone: str = ""
    website: str = ""
    google_maps_url: str = ""
    latitude: float | None = None
    longitude: float | None = None
    place_id: str = ""
    primary_type: str = ""
    business_status: str = ""
    service_area_business: bool = False
    zone_index: int = 0
    zone_latitude: float = 0.0
    zone_longitude: float = 0.0
    distance_km: float | None = None
    radius_verified: bool = True
    collected_at: datetime | None = None


@dataclass(slots=True)
class SearchStats:
    api_calls: int = 0
    zones_searched: int = 0
    pages_fetched: int = 0
    raw_results: int = 0
    duplicates_removed: int = 0
    outside_radius_removed: int = 0
    service_area_unverified: int = 0
    target_reached: bool = False


@dataclass(frozen=True, slots=True)
class SearchResult:
    leads: list[Lead] = field(default_factory=list)
    stats: SearchStats = field(default_factory=SearchStats)
    generated_at: datetime | None = None
