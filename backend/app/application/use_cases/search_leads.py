from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from ...domain.geo import SearchTile, generate_tiles, haversine_km
from ...domain.lead import Lead, SearchResult, SearchStats
from ..models import SearchCriteria
from ..ports.places import PlaceCandidate, PlacesGateway


class SearchLeadsUseCase:
    def __init__(self, places: PlacesGateway) -> None:
        self._places = places

    async def execute(self, criteria: SearchCriteria) -> SearchResult:
        stats = SearchStats()
        leads: list[Lead] = []
        seen_place_ids: set[str] = set()
        seen_fallback: set[str] = set()
        collected_at = datetime.now(timezone.utc)
        tiles = generate_tiles(
            criteria.center_latitude,
            criteria.center_longitude,
            criteria.radius_km,
            criteria.max_tiles,
        )

        for tile in tiles:
            stats.zones_searched += 1
            page_token: str | None = None
            for _ in range(criteria.max_pages):
                page = await self._places.search_page(criteria, tile, page_token)
                stats.api_calls += 1
                stats.pages_fetched += 1
                stats.raw_results += len(page.places)

                for place in page.places:
                    lead = self._to_lead(place, criteria, tile, collected_at)
                    if not lead.radius_verified:
                        if not criteria.include_service_area_businesses:
                            stats.outside_radius_removed += 1
                            continue
                        stats.service_area_unverified += 1
                    elif lead.distance_km is not None and lead.distance_km > criteria.radius_km:
                        stats.outside_radius_removed += 1
                        continue

                    fallback = self._fallback_key(lead)
                    duplicate = (lead.place_id and lead.place_id in seen_place_ids) or (
                        not lead.place_id and fallback in seen_fallback
                    )
                    if duplicate:
                        stats.duplicates_removed += 1
                        continue

                    if lead.place_id:
                        seen_place_ids.add(lead.place_id)
                    else:
                        seen_fallback.add(fallback)
                    leads.append(lead)
                    if len(leads) >= criteria.target:
                        stats.target_reached = True
                        return SearchResult(leads=leads, stats=stats, generated_at=collected_at)

                page_token = page.next_page_token
                if not page_token:
                    break

        return SearchResult(leads=leads, stats=stats, generated_at=collected_at)

    @staticmethod
    def _to_lead(
        place: PlaceCandidate,
        criteria: SearchCriteria,
        tile: SearchTile,
        collected_at: datetime,
    ) -> Lead:
        has_location = place.latitude is not None and place.longitude is not None
        distance = (
            round(
                haversine_km(
                    criteria.center_latitude,
                    criteria.center_longitude,
                    float(place.latitude),
                    float(place.longitude),
                ),
                3,
            )
            if has_location
            else None
        )
        return Lead(
            name=place.name,
            address=place.address,
            phone=place.phone,
            international_phone=place.international_phone,
            website=place.website,
            google_maps_url=place.google_maps_url,
            latitude=float(place.latitude) if has_location else None,
            longitude=float(place.longitude) if has_location else None,
            place_id=place.place_id,
            primary_type=place.primary_type,
            business_status=place.business_status,
            service_area_business=place.service_area_business,
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
