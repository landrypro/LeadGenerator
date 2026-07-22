from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ....application.errors import (
    InvalidMapSnapshotGrant,
    MapSnapshotGrantInProgress,
    StaticMapProviderError,
)
from ..dependencies import ContainerDependency
from ..schemas import MapSnapshotTokenRequest

router = APIRouter(prefix="/api/map", tags=["maps"])


@router.post("/snapshot")
async def map_snapshot(payload: MapSnapshotTokenRequest, container: ContainerDependency) -> Response:
    if not container.settings.static_maps_api_key:
        raise HTTPException(
            status_code=503,
            detail="Aucune clé Google Maps n’est configurée pour la carte.",
        )
    try:
        image = await container.get_map_snapshot.execute(payload.token)
        return Response(
            content=image.content,
            media_type=image.media_type,
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    except InvalidMapSnapshotGrant as exc:
        raise HTTPException(
            status_code=403,
            detail="Le jeton de carte est invalide ou expiré.",
        ) from exc
    except MapSnapshotGrantInProgress as exc:
        raise HTTPException(
            status_code=409,
            detail="Cette carte est déjà en cours de génération.",
        ) from exc
    except StaticMapProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
