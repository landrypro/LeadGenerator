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
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(container: ContainerDependency) -> JSONResponse:
    report = await container.readiness.execute()
    content = {
        "status": "ready" if report.is_ready else "not_ready",
        "dependencies": {dependency.name: dependency.state for dependency in report.dependencies},
    }
    return JSONResponse(status_code=200 if report.is_ready else 503, content=content)
