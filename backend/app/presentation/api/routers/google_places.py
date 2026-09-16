from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    GoogleProtectionUnavailable,
    GoogleQuotaExceeded,
    GoogleSearchInProgress,
    MapSnapshotGrantCapacityReached,
    PlacesProviderError,
)
from ..dependencies import ContainerDependency
from ..google_access import google_access_error, required_google_access
from ..mappers import to_search_criteria, to_search_response
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import GooglePlaceSearchRequest, GooglePlaceSearchResponse

router = APIRouter(prefix="/api/google/places", tags=["google-places"])


@router.post("/search", response_model=GooglePlaceSearchResponse)
async def search_google_places(
    payload: GooglePlaceSearchRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        access = await required_google_access(request, container, "google:search")
        if not container.settings.google_maps_api_key:
            return api_error(
                request,
                503,
                "google_not_configured",
                "La recherche Google n’est pas configurée.",
            )
        result = await container.search_google_places.execute(to_search_criteria(payload), access)
    except Exception as error:
        response = google_access_error(request, error)
        if response is not None:
            return response
        if isinstance(error, GoogleSearchInProgress):
            return api_error(
                request,
                409,
                "google_search_in_progress",
                "Une recherche Google est déjà en cours pour ce compte.",
            )
        if isinstance(error, GoogleQuotaExceeded):
            return api_error(
                request,
                429,
                "google_quota_exceeded",
                "La limite quotidienne de recherches Google est atteinte. Réessayez après la remise à zéro.",
                fields={"scope": error.scope},
                headers={"Retry-After": str(error.retry_after_seconds)},
            )
        if isinstance(error, GoogleProtectionUnavailable):
            return api_error(
                request,
                503,
                "google_protection_unavailable",
                "La protection temporaire du parcours Google est indisponible.",
            )
        if isinstance(error, MapSnapshotGrantCapacityReached):
            return api_error(
                request,
                503,
                "map_grant_unavailable",
                "La carte est temporairement indisponible.",
            )
        if isinstance(error, PlacesProviderError):
            if error.status_code == 429:
                return api_error(request, 429, "google_rate_limited", "Google limite temporairement les recherches.")
            return api_error(
                request,
                502,
                "google_places_unavailable",
                "Google Places est temporairement indisponible.",
            )
        raise
    response_payload = to_search_response(result, payload)
    return JSONResponse(response_payload.model_dump(mode="json"), headers=NO_STORE_HEADERS)
