from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from .geo import SearchTile
from .models import SearchRequest

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
BASE_FIELDS = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.googleMapsUri,places.primaryType,places.businessStatus,places.pureServiceAreaBusiness,"
    "nextPageToken"
)
CONTACT_FIELDS = ",places.nationalPhoneNumber,places.internationalPhoneNumber,places.websiteUri"


@dataclass(frozen=True)
class GooglePlacesSettings:
    api_key: str
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_base_seconds: float = 0.4


@dataclass(frozen=True)
class PlacesPage:
    places: list[dict[str, Any]]
    next_page_token: str | None


class GooglePlacesError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GooglePlacesClient:
    def __init__(self, settings: GooglePlacesSettings, http_client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = http_client

    async def search_page(
        self,
        request: SearchRequest,
        tile: SearchTile,
        page_token: str | None = None,
    ) -> PlacesPage:
        body: dict[str, Any] = {
            "textQuery": request.query,
            "languageCode": request.language_code,
            "regionCode": request.region_code,
            "pageSize": 20,
            "includePureServiceAreaBusinesses": request.include_service_area_businesses,
            "locationBias": {
                "circle": {
                    "center": {"latitude": tile.latitude, "longitude": tile.longitude},
                    "radius": tile.bias_radius_m,
                }
            },
        }
        if page_token:
            body["pageToken"] = page_token

        headers = {
            "X-Goog-Api-Key": self.settings.api_key,
            "X-Goog-FieldMask": BASE_FIELDS + (CONTACT_FIELDS if request.contact_fields else ""),
            "Content-Type": "application/json",
        }
        response = await self._post_with_retry(body, headers)
        payload = response.json()
        return PlacesPage(payload.get("places", []), payload.get("nextPageToken"))

    async def _post_with_retry(self, body: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.timeout_seconds)
        try:
            for attempt in range(self.settings.max_retries + 1):
                try:
                    response = await client.post(PLACES_URL, json=body, headers=headers)
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt >= self.settings.max_retries:
                        raise GooglePlacesError("Google Places est temporairement injoignable.") from exc
                    await asyncio.sleep(self.settings.retry_base_seconds * (2**attempt))
                    continue

                retryable = response.status_code == 429 or response.status_code >= 500
                if retryable and attempt < self.settings.max_retries:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else self.settings.retry_base_seconds * (2**attempt)
                    await asyncio.sleep(delay)
                    continue

                if response.is_error:
                    try:
                        detail = response.json().get("error", {}).get("message", response.text)
                    except ValueError:
                        detail = response.text
                    raise GooglePlacesError(f"Google Places a refusé la requête : {detail}", response.status_code)
                return response
        finally:
            if owns_client:
                await client.aclose()
        raise GooglePlacesError("La requête Google Places a échoué après plusieurs tentatives.")

