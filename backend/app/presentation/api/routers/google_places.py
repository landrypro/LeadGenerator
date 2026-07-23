from fastapi import APIRouter, HTTPException, Response

from ....application.errors import AddressGenerationInProgress, PlacesProviderError
from ..dependencies import ContainerDependency
from ..mappers import to_search_criteria, to_search_response
from ..schemas import GooglePlaceSearchRequest, GooglePlaceSearchResponse

router = APIRouter(prefix="/api/google/places", tags=["google-places"])
NO_STORE_HEADERS = {"Cache-Control": "no-store, max-age=0"}


@router.post("/search", response_model=GooglePlaceSearchResponse)
async def search_google_places(
    request: GooglePlaceSearchRequest,
    response: Response,
    container: ContainerDependency,
) -> GooglePlaceSearchResponse:
    response.headers.update(NO_STORE_HEADERS)
    if not container.settings.google_maps_api_key:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_MAPS_API_KEY n’est pas configurée sur le serveur.",
            headers=NO_STORE_HEADERS,
        )
    try:
        result = await container.search_google_places.execute(
            to_search_criteria(request),
            request.requester.business_address,
        )
        return to_search_response(result, request)
    except AddressGenerationInProgress as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Une recherche est déjà en cours pour cette adresse professionnelle. "
                "Réessayez lorsqu’elle sera terminée."
            ),
            headers=NO_STORE_HEADERS,
        ) from exc
    except PlacesProviderError as exc:
        status = 429 if exc.status_code == 429 else 502
        raise HTTPException(
            status_code=status,
            detail=str(exc),
            headers=NO_STORE_HEADERS,
        ) from exc
