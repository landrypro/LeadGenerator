from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class GooglePlaceSummary:
    """Vue temporaire et sans coordonnées de contact d’un résultat Google."""

    place_id: str
    name: str = ""
    address: str = ""
    google_maps_url: str = ""
    latitude: float | None = None
    longitude: float | None = None
    primary_type: str = ""
    business_status: str = ""
    service_area_business: bool = False
    distance_km: float | None = None
    radius_verified: bool = True


@dataclass(frozen=True, slots=True)
class GooglePlaceSearchStats:
    api_calls: int
    raw_results: int
    displayed_results: int
    duplicates_removed: int = 0
    outside_radius_removed: int = 0
    service_area_unverified: int = 0


@dataclass(frozen=True, slots=True)
class GooglePlaceSearchResult:
    searched_at: datetime
    places: list[GooglePlaceSummary] = field(default_factory=list)
    stats: GooglePlaceSearchStats = field(
        default_factory=lambda: GooglePlaceSearchStats(
            api_calls=1,
            raw_results=0,
            displayed_results=0,
        )
    )
