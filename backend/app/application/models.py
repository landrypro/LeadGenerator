from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

GOOGLE_QUOTA_POLICY_CODE_PATTERN = re.compile(r"[a-z0-9_]{3,64}")


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
class GoogleSearchQuotaPolicy:
    """Politique serveur de coût Google, distincte d'un futur plan commercial."""

    enabled: bool
    user_daily_limit: int
    organization_daily_limit: int
    warning_threshold_percent: int
    policy_code: str

    def __post_init__(self) -> None:
        limits = (self.user_daily_limit, self.organization_daily_limit)
        if not isinstance(self.enabled, bool) or any(
            isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 10_000 for limit in limits
        ):
            raise ValueError("La politique de quota Google est invalide.")
        if (
            isinstance(self.warning_threshold_percent, bool)
            or not isinstance(self.warning_threshold_percent, int)
            or not 1 <= self.warning_threshold_percent <= 100
            or not GOOGLE_QUOTA_POLICY_CODE_PATTERN.fullmatch(self.policy_code)
        ):
            raise ValueError("La politique de quota Google est invalide.")


@dataclass(frozen=True, slots=True)
class GoogleQuotaReservation:
    """Résultat minimal d'une réservation atomique de recherche Google."""

    allowed: bool
    scope: Literal["user", "organization"] | None
    user_used: int
    user_remaining: int
    organization_used: int
    organization_remaining: int
    reset_at: datetime
    retry_after_seconds: int
    policy_code: str
    user_warning_created: bool = False
    organization_warning_created: bool = False


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
