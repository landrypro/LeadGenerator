from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from ....application.errors import (
    GoogleProtectionUnavailable,
    GoogleQuotaExceeded,
    GoogleSearchInProgress,
    MapSnapshotGrantCapacityReached,
    PlacesProviderError,
    UsageTrackingUnavailable,
)
from ....application.models import GoogleAccessContext
from ....application.ports.usage import UsageEvent
from ....application.tenancy import TenantContext
from ....infrastructure.google.location import InvalidLocationSelection
from ....infrastructure.google.places import GooglePlacesError
from ..dependencies import ContainerDependency
from ..google_access import google_access_error, required_google_access
from ..mappers import to_search_criteria, to_search_response
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import (
    GoogleLocationResolveRequest,
    GoogleLocationSuggestRequest,
    GooglePlaceSearchRequest,
    GooglePlaceSearchResponse,
)

router = APIRouter(prefix="/api/google/places", tags=["google-places"])


async def _location_usage(
    container: ContainerDependency,
    access: GoogleAccessContext,
    operation_id: UUID,
    usage_code: str,
    event_kind: str,
    outcome: str,
) -> None:
    if container.usage_store is None:
        raise UsageTrackingUnavailable
    await container.usage_store.record(
        UsageEvent(
            context=TenantContext(access.user_id, access.organization_id, f"usage:{operation_id}"),
            membership_id=access.membership_id,
            operation_id=operation_id,
            usage_code=usage_code,
            event_kind=event_kind,
            outcome=outcome,
            occurred_at=datetime.now(UTC),
        )
    )


@router.post("/locations/suggest")
async def suggest_google_locations(
    payload: GoogleLocationSuggestRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        access = await required_google_access(request, container, "google:search")
        if not container.settings.google_maps_api_key or container.location_resolver is None:
            return api_error(request, 503, "google_not_configured", "La recherche Google n’est pas configurée.")
        operation_id = uuid4()
        attempted = False
        upstream_started_at = 0.0

        async def record_attempt() -> None:
            nonlocal attempted, upstream_started_at
            await _location_usage(
                container,
                access,
                operation_id,
                "google.places_autocomplete.request",
                "upstream_attempted",
                "attempted",
            )
            attempted = True
            upstream_started_at = perf_counter()

        try:
            items = await container.location_resolver.suggest(
                text=payload.text.strip(),
                area=payload.area.strip(),
                scope=payload.scope,
                language=payload.language,
                session_token=payload.session_token,
                access=access,
                country_code=payload.country_code,
                before_upstream=record_attempt,
            )
        except Exception:
            if attempted:
                container.metrics.record_google_upstream(
                    "places_autocomplete", "failed", perf_counter() - upstream_started_at
                )
                await _location_usage(
                    container,
                    access,
                    operation_id,
                    "google.places_autocomplete.request",
                    "upstream_failed",
                    "failed",
                )
            raise
        container.metrics.record_google_upstream(
            "places_autocomplete", "accepted", perf_counter() - upstream_started_at
        )
        await _location_usage(
            container, access, operation_id, "google.places_autocomplete.request", "upstream_succeeded", "succeeded"
        )
    except Exception as error:
        response = google_access_error(request, error)
        if response is not None:
            return response
        if isinstance(error, GooglePlacesError):
            status = 429 if error.status_code == 429 else 503 if error.status_code is None else 502
            if status == 429:
                return api_error(
                    request,
                    status,
                    "google_location_rate_limited",
                    "Trop de recherches de lieux.",
                    headers={"Retry-After": "60"},
                )
            return api_error(request, status, "google_location_unavailable", str(error))
        if isinstance(error, UsageTrackingUnavailable):
            return api_error(
                request, 503, "usage_tracking_unavailable", "Le registre d’usage est temporairement indisponible."
            )
        raise
    return JSONResponse({"items": items}, headers=NO_STORE_HEADERS)


@router.post("/locations/resolve")
async def resolve_google_location(
    payload: GoogleLocationResolveRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        access = await required_google_access(request, container, "google:search")
        if not container.settings.google_maps_api_key or container.location_resolver is None:
            return api_error(request, 503, "google_not_configured", "La recherche Google n’est pas configurée.")
        operation_id = uuid4()
        attempted = False
        upstream_started_at = 0.0

        async def record_attempt() -> None:
            nonlocal attempted, upstream_started_at
            await _location_usage(
                container,
                access,
                operation_id,
                "google.places_details.request",
                "upstream_attempted",
                "attempted",
            )
            attempted = True
            upstream_started_at = perf_counter()

        try:
            place = await container.location_resolver.resolve(
                selection_token=payload.selection_token,
                access=access,
                before_upstream=record_attempt,
            )
        except Exception:
            if attempted:
                container.metrics.record_google_upstream(
                    "places_details", "failed", perf_counter() - upstream_started_at
                )
                await _location_usage(
                    container,
                    access,
                    operation_id,
                    "google.places_details.request",
                    "upstream_failed",
                    "failed",
                )
            raise
        container.metrics.record_google_upstream("places_details", "accepted", perf_counter() - upstream_started_at)
        await _location_usage(
            container, access, operation_id, "google.places_details.request", "upstream_succeeded", "succeeded"
        )
    except Exception as error:
        response = google_access_error(request, error)
        if response is not None:
            return response
        if isinstance(error, InvalidLocationSelection):
            return api_error(request, 400, "invalid_location_selection", str(error))
        if isinstance(error, GooglePlacesError):
            status = 429 if error.status_code == 429 else 503 if error.status_code is None else 502
            if status == 429:
                return api_error(
                    request,
                    status,
                    "google_location_rate_limited",
                    "Trop de recherches de lieux.",
                    headers={"Retry-After": "60"},
                )
            return api_error(request, status, "google_location_unavailable", str(error))
        if isinstance(error, UsageTrackingUnavailable):
            return api_error(
                request, 503, "usage_tracking_unavailable", "Le registre d’usage est temporairement indisponible."
            )
        raise
    return JSONResponse(place, headers=NO_STORE_HEADERS)


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
        if isinstance(error, UsageTrackingUnavailable):
            return api_error(
                request, 503, "usage_tracking_unavailable", "Le registre d’usage est temporairement indisponible."
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
