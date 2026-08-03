from fastapi import APIRouter, Request
from fastapi.responses import Response

from ....application.errors import InvalidMapSnapshotGrant, MapSnapshotGrantInProgress, StaticMapProviderError
from ..dependencies import ContainerDependency
from ..google_access import google_access_error, required_google_access
from ..responses import NO_STORE_HEADERS, api_error
from ..schemas import MapSnapshotTokenRequest

router = APIRouter(prefix="/api/map", tags=["maps"])


@router.post("/snapshot")
async def map_snapshot(
    payload: MapSnapshotTokenRequest,
    request: Request,
    container: ContainerDependency,
) -> Response:
    try:
        access = await required_google_access(request, container, "google:map")
        if not container.settings.static_maps_api_key:
            return api_error(
                request,
                503,
                "google_not_configured",
                "La carte Google n’est pas configurée.",
            )
        image = await container.get_map_snapshot.execute(payload.token, access)
    except Exception as error:
        response = google_access_error(request, error)
        if response is not None:
            return response
        if isinstance(error, InvalidMapSnapshotGrant):
            return api_error(
                request,
                403,
                "invalid_map_grant",
                "La concession de carte est invalide ou expirée.",
            )
        if isinstance(error, MapSnapshotGrantInProgress):
            return api_error(
                request,
                409,
                "map_grant_in_progress",
                "Cette carte est déjà en cours de génération.",
            )
        if isinstance(error, StaticMapProviderError):
            return api_error(
                request,
                502,
                "google_map_unavailable",
                "Google Maps est temporairement indisponible.",
            )
        raise
    return Response(content=image.content, media_type=image.media_type, headers=NO_STORE_HEADERS)
