from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..dependencies import ContainerDependency

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(container: ContainerDependency) -> dict[str, bool | str]:
    google_places_mode = "simulated" if container.settings.google_places_simulator_enabled else "live"
    return {
        "status": "ok",
        "google_api_key_configured": container.settings.google_places_search_available,
        "google_places_mode": google_places_mode,
    }


@router.get("/health/live")
async def liveness(container: ContainerDependency) -> dict[str, object]:
    settings = container.settings
    return {
        "status": "ok",
        "release": {
            "version": settings.app_version,
            "git_sha": settings.release_git_sha or "unknown",
            "image_digest": settings.release_image_digest or "unknown",
        },
    }


@router.get("/health/ready")
async def readiness(container: ContainerDependency) -> JSONResponse:
    report = await container.readiness.execute()
    content = {
        "status": "ready" if report.is_ready else "not_ready",
        "dependencies": {dependency.name: dependency.state for dependency in report.dependencies},
        "release": {
            "version": container.settings.app_version,
            "git_sha": container.settings.release_git_sha or "unknown",
            "image_digest": container.settings.release_image_digest or "unknown",
        },
    }
    return JSONResponse(status_code=200 if report.is_ready else 503, content=content)
