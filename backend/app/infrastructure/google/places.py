from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ...application.errors import PlacesProviderError
from ...application.models import GooglePlaceSearchCriteria
from ...application.ports.places import PlaceCandidate

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
PAGE_SIZE = 20
PLACE_LIST_FIELDS = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.googleMapsUri,places.primaryType,places.businessStatus,places.pureServiceAreaBusiness"
)


@dataclass(frozen=True)
class GooglePlacesSettings:
    api_key: str
    timeout_seconds: float = 30.0


class GooglePlacesError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GooglePlacesClient:
    """Client Text Search effectuant exactement un POST par recherche utilisateur."""

    def __init__(self, settings: GooglePlacesSettings, http_client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = http_client

    async def search(self, request: GooglePlaceSearchCriteria) -> list[dict[str, Any]]:
        body: dict[str, Any] = {
            "textQuery": request.query,
            "languageCode": request.language_code,
            "regionCode": request.region_code,
            "pageSize": PAGE_SIZE,
            "includePureServiceAreaBusinesses": request.include_service_area_businesses,
            "locationBias": {
                "circle": {
                    "center": {
                        "latitude": request.center_latitude,
                        "longitude": request.center_longitude,
                    },
                    "radius": request.radius_km * 1_000,
                }
            },
        }
        headers = {
            "X-Goog-Api-Key": self.settings.api_key,
            "X-Goog-FieldMask": PLACE_LIST_FIELDS,
            "Content-Type": "application/json",
        }
        response = await self._post_once(body, headers)
        places = response.json().get("places", [])
        return places[:PAGE_SIZE] if isinstance(places, list) else []

    async def _post_once(self, body: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.timeout_seconds)
        try:
            try:
                response = await client.post(PLACES_URL, json=body, headers=headers)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise GooglePlacesError("Google Places est temporairement injoignable.") from exc
        finally:
            if owns_client:
                await client.aclose()

        if response.is_error:
            try:
                detail = response.json().get("error", {}).get("message", response.text)
            except ValueError:
                detail = response.text
            raise GooglePlacesError(
                f"Google Places a refusé la requête : {detail}",
                response.status_code,
            )
        return response


class GooglePlacesGateway:
    """Adapte la réponse Google temporaire au port applicatif sans contacts."""

    def __init__(self, client: GooglePlacesClient) -> None:
        self._client = client

    async def search(self, criteria: GooglePlaceSearchCriteria) -> list[PlaceCandidate]:
        try:
            places = await self._client.search(criteria)
        except GooglePlacesError as exc:
            raise PlacesProviderError(str(exc), exc.status_code) from exc
        return [google_place_to_candidate(place) for place in places]


def google_place_to_candidate(place: dict[str, Any]) -> PlaceCandidate:
    location = place.get("location") or {}
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    display_name = place.get("displayName") or {}
    parsed_latitude = float(latitude) if isinstance(latitude, int | float) else None
    parsed_longitude = float(longitude) if isinstance(longitude, int | float) else None
    return PlaceCandidate(
        place_id=place.get("id", ""),
        name=display_name.get("text", ""),
        address=place.get("formattedAddress", ""),
        google_maps_url=place.get("googleMapsUri", ""),
        latitude=parsed_latitude if parsed_longitude is not None else None,
        longitude=parsed_longitude if parsed_latitude is not None else None,
        primary_type=place.get("primaryType", ""),
        business_status=place.get("businessStatus", ""),
        service_area_business=bool(place.get("pureServiceAreaBusiness", False)),
    )
