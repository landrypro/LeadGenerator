from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .application.use_cases import (
    ExportLeadsUseCase,
    GenerateLeadsUseCase,
    GetMapSnapshotUseCase,
    SearchLeadsUseCase,
)
from .config import Settings
from .container import AppContainer
from .infrastructure.export.excel import ExcelLeadExporter
from .infrastructure.google.places import (
    GooglePlacesClient,
    GooglePlacesGateway,
    GooglePlacesSettings,
)
from .infrastructure.google.static_maps import GoogleStaticMapGateway
from .infrastructure.memory import InMemoryGenerationGuard, InMemoryMapSnapshotGrantStore
from .presentation.api.routers import health_router, leads_router, maps_router


def build_container(settings: Settings) -> AppContainer:
    places_client = GooglePlacesClient(
        GooglePlacesSettings(
            api_key=settings.google_maps_api_key,
            timeout_seconds=settings.places_timeout_seconds,
            max_retries=settings.places_max_retries,
            retry_base_seconds=settings.places_retry_base_seconds,
        )
    )
    places_gateway = GooglePlacesGateway(places_client)
    generation_guard = InMemoryGenerationGuard()
    map_grants = InMemoryMapSnapshotGrantStore(
        ttl_seconds=settings.map_grant_ttl_seconds,
        max_grants=settings.map_grant_max_entries,
    )
    static_maps = GoogleStaticMapGateway(
        api_key=settings.static_maps_api_key,
        timeout_seconds=settings.static_maps_timeout_seconds,
    )

    search_leads = SearchLeadsUseCase(places_gateway)
    return AppContainer(
        settings=settings,
        generate_leads=GenerateLeadsUseCase(search_leads, generation_guard, map_grants),
        export_leads=ExportLeadsUseCase(ExcelLeadExporter()),
        get_map_snapshot=GetMapSnapshotUseCase(map_grants, static_maps),
    )


def create_app(
    settings: Settings | None = None,
    container: AppContainer | None = None,
) -> FastAPI:
    if settings is not None and container is not None and settings != container.settings:
        raise ValueError("Le conteneur injecté et create_app() doivent utiliser les mêmes Settings.")
    resolved_settings = settings or (container.settings if container else Settings.from_env())
    resolved_container = container or build_container(resolved_settings)

    app = FastAPI(
        title=resolved_settings.app_title,
        version=resolved_settings.app_version,
    )
    app.state.container = resolved_container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(leads_router)
    app.include_router(maps_router)

    frontend_dist = Path(__file__).resolve().parents[2] / "client" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return app
