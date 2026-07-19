from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Protocol

from .geo import SearchTile, generate_tiles, haversine_km
from .models import Lead, SearchRequest, SearchResponse, SearchStats
from .places import PlacesPage


class PlacesClient(Protocol):
    async def search_page(self, request: SearchRequest, tile: SearchTile, page_token: str | None = None) -> PlacesPage: ...


class LeadSearchService:
    def __init__(self, client: PlacesClient) -> None:
        self.client = client

    async def search(self, request: SearchRequest) -> SearchResponse:
        stats = SearchStats()
        leads: list[Lead] = []
        seen_place_ids: set[str] = set()
        seen_fallback: set[str] = set()
        collected_at = datetime.now(timezone.utc)
        tiles = generate_tiles(request.center_latitude, request.center_longitude, request.radius_km, request.max_tiles)

        for tile in tiles:
            stats.zones_searched += 1
            page_token: str | None = None
            for _ in range(request.max_pages):
                page = await self.client.search_page(request, tile, page_token)
                stats.api_calls += 1
                stats.pages_fetched += 1
                stats.raw_results += len(page.places)

                for place in page.places:
                    lead = self._to_lead(place, request, tile, collected_at)
                    if not lead.radius_verified:
                        if not request.include_service_area_businesses:
                            stats.outside_radius_removed += 1
                            continue
                        stats.service_area_unverified += 1
                    elif lead.distance_km is not None and lead.distance_km > request.radius_km:
                        stats.outside_radius_removed += 1
                        continue

                    fallback = self._fallback_key(lead)
                    duplicate = (lead.place_id and lead.place_id in seen_place_ids) or (not lead.place_id and fallback in seen_fallback)
                    if duplicate:
                        stats.duplicates_removed += 1
                        continue

                    if lead.place_id:
                        seen_place_ids.add(lead.place_id)
                    else:
                        seen_fallback.add(fallback)
                    leads.append(lead)
                    if len(leads) >= request.target:
                        stats.target_reached = True
                        return SearchResponse(leads=leads, stats=stats, generated_at=collected_at)

                page_token = page.next_page_token
                if not page_token:
                    break

        return SearchResponse(leads=leads, stats=stats, generated_at=collected_at)

    @staticmethod
    def _to_lead(place: dict, request: SearchRequest, tile: SearchTile, collected_at: datetime) -> Lead:
        location = place.get("location") or {}
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        has_location = latitude is not None and longitude is not None
        distance = (
            round(haversine_km(request.center_latitude, request.center_longitude, float(latitude), float(longitude)), 3)
            if has_location
            else None
        )
        display_name = place.get("displayName") or {}
        return Lead(
            name=display_name.get("text", ""),
            address=place.get("formattedAddress", ""),
            phone=place.get("nationalPhoneNumber", ""),
            international_phone=place.get("internationalPhoneNumber", ""),
            website=place.get("websiteUri", ""),
            google_maps_url=place.get("googleMapsUri", ""),
            latitude=float(latitude) if has_location else None,
            longitude=float(longitude) if has_location else None,
            place_id=place.get("id", ""),
            primary_type=place.get("primaryType", ""),
            business_status=place.get("businessStatus", ""),
            service_area_business=bool(place.get("pureServiceAreaBusiness", False)),
            zone_index=tile.index,
            zone_latitude=tile.latitude,
            zone_longitude=tile.longitude,
            distance_km=distance,
            radius_verified=has_location,
            collected_at=collected_at,
        )

    @staticmethod
    def _fallback_key(lead: Lead) -> str:
        raw = f"{lead.name}|{lead.address}".lower()
        normalized = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "", normalized)

