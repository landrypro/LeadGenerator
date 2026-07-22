from fastapi import APIRouter

from ..dependencies import ContainerDependency

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(container: ContainerDependency) -> dict[str, bool | str]:
    return {
        "status": "ok",
        "google_api_key_configured": bool(container.settings.google_maps_api_key),
    }
