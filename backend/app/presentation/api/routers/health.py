from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..dependencies import ContainerDependency

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(container: ContainerDependency) -> dict[str, bool | str]:
    return {
        "status": "ok",
        "google_api_key_configured": bool(container.settings.google_maps_api_key),
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
