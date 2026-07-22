from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RequesterInfo(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    company_name: str = Field(min_length=2, max_length=160)
    business_address: str = Field(min_length=5, max_length=240)

    @field_validator("first_name", "company_name", "business_address")
    @classmethod
    def clean_identity_field(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Ce champ est requis.")
        return value


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=120)
    center_latitude: float = Field(default=46.8139, ge=-90, le=90)
    center_longitude: float = Field(default=-71.2080, ge=-180, le=180)
    radius_km: float = Field(default=15, gt=0, le=50)
    target: int = Field(default=200, ge=1, le=500)
    max_tiles: int = Field(default=8, ge=1, le=30)
    max_pages: int = Field(default=3, ge=1, le=3)
    contact_fields: bool = False
    include_service_area_businesses: bool = True
    language_code: str = Field(default="fr", min_length=2, max_length=10)
    region_code: str = Field(default="CA", min_length=2, max_length=2)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Le terme de recherche est requis.")
        return value

    @field_validator("region_code")
    @classmethod
    def normalize_region(cls, value: str) -> str:
        return value.upper()


class LeadGenerationRequest(SearchRequest):
    requester: RequesterInfo


class Lead(BaseModel):
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
    zone_index: int
    zone_latitude: float
    zone_longitude: float
    distance_km: float | None = None
    radius_verified: bool = True
    collected_at: datetime


class SearchStats(BaseModel):
    api_calls: int = 0
    zones_searched: int = 0
    pages_fetched: int = 0
    raw_results: int = 0
    duplicates_removed: int = 0
    outside_radius_removed: int = 0
    service_area_unverified: int = 0
    target_reached: bool = False


class SearchResponse(BaseModel):
    leads: list[Lead]
    stats: SearchStats
    generated_at: datetime


class LeadGenerationResponse(SearchResponse):
    map_snapshot_token: str
    search_parameters: SearchRequest


class ExportRequest(BaseModel):
    leads: list[Lead] = Field(max_length=1000)
    search: dict[str, Any] = Field(default_factory=dict)


class MapPoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class MapSnapshotRequest(BaseModel):
    center_latitude: float = Field(ge=-90, le=90)
    center_longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=50)
    points: list[MapPoint] = Field(default_factory=list, max_length=50)


class MapSnapshotTokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)
