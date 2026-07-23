from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .application.ports import AsyncResource, DependencyProbe, UnitOfWorkFactory
from .application.use_cases import (
    CheckReadinessUseCase,
    GetCurrentSessionUseCase,
    GetMapSnapshotUseCase,
    LoginUseCase,
    LogoutUseCase,
    SearchGooglePlacesUseCase,
)
from .config import Settings
from .container import AppContainer
from .infrastructure.clock import SystemClock
from .infrastructure.google.places import (
    GooglePlacesClient,
    GooglePlacesGateway,
    GooglePlacesSettings,
)
from .infrastructure.google.static_maps import GoogleStaticMapGateway
from .infrastructure.health import UnconfiguredDependencyProbe
from .infrastructure.memory import InMemoryGenerationGuard, InMemoryMapSnapshotGrantStore
from .infrastructure.postgres import PostgresDatabase
from .infrastructure.redis import RedisLoginRateLimiter, RedisResource, RedisSessionStore
from .infrastructure.security import Argon2PasswordHasher
from .presentation.api.routers import auth_router, google_places_router, health_router, maps_router


def build_container(settings: Settings) -> AppContainer:
    probes: list[DependencyProbe] = []
    resources: list[AsyncResource] = []
    unit_of_work_factory: UnitOfWorkFactory | None = None
    database: PostgresDatabase | None = None
    redis: RedisResource | None = None

    if settings.database_url:
        database = PostgresDatabase(
            settings.database_url,
            connect_timeout_seconds=settings.dependency_connect_timeout_seconds,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout_seconds=settings.database_pool_timeout_seconds,
            statement_timeout_ms=settings.database_statement_timeout_ms,
        )
        probes.append(database)
        resources.append(database)
        unit_of_work_factory = database.unit_of_work
    else:
        probes.append(UnconfiguredDependencyProbe("postgresql"))

    if settings.redis_url:
        redis = RedisResource(
            settings.redis_url,
            connect_timeout_seconds=settings.dependency_connect_timeout_seconds,
            max_connections=settings.redis_max_connections,
        )
        probes.append(redis)
        resources.append(redis)
    else:
        probes.append(UnconfiguredDependencyProbe("redis"))

    places_client = GooglePlacesClient(
        GooglePlacesSettings(
            api_key=settings.google_maps_api_key,
            timeout_seconds=settings.places_timeout_seconds,
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

    login: LoginUseCase | None = None
    get_current_session: GetCurrentSessionUseCase | None = None
    logout: LogoutUseCase | None = None
    if database is not None and redis is not None:
        clock = SystemClock()
        session_store = RedisSessionStore(
            redis.client,
            environment=settings.app_env,
            idle_seconds=settings.session_idle_seconds,
            absolute_seconds=settings.session_absolute_seconds,
        )
        login_rate_limiter = RedisLoginRateLimiter(
            redis.client,
            environment=settings.app_env,
            window_seconds=settings.login_rate_limit_window_seconds,
            pair_limit=settings.login_rate_limit_pair_failures,
            address_limit=settings.login_rate_limit_address_failures,
        )
        login = LoginUseCase(
            database.identity_unit_of_work,
            Argon2PasswordHasher(),
            session_store,
            login_rate_limiter,
            clock,
        )
        get_current_session = GetCurrentSessionUseCase(database.identity_unit_of_work, session_store, clock)
        logout = LogoutUseCase(session_store, clock)

    return AppContainer(
        settings=settings,
        search_google_places=SearchGooglePlacesUseCase(
            places_gateway,
            generation_guard,
            map_grants,
        ),
        get_map_snapshot=GetMapSnapshotUseCase(map_grants, static_maps),
        readiness=CheckReadinessUseCase(probes),
        login=login,
        get_current_session=get_current_session,
        logout=logout,
        unit_of_work_factory=unit_of_work_factory,
        resources=tuple(resources),
    )


def create_app(
    settings: Settings | None = None,
    container: AppContainer | None = None,
) -> FastAPI:
    if settings is not None and container is not None and settings != container.settings:
        raise ValueError("Le conteneur injecté et create_app() doivent utiliser les mêmes Settings.")
    resolved_settings = settings or (container.settings if container else Settings.from_env())
    resolved_container = container or build_container(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await resolved_container.close()

    app = FastAPI(
        title=resolved_settings.app_title,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    app.state.container = resolved_container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.middleware("http")(_add_request_id)

    @app.exception_handler(RequestValidationError)
    async def sanitized_auth_validation_error(request: Request, error: RequestValidationError) -> Response:
        if not request.url.path.startswith("/api/auth/"):
            return await request_validation_exception_handler(request, error)
        fields = {str(item["loc"][-1]): "Valeur invalide." for item in error.errors() if item.get("loc")}
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_failed",
                    "message": "La requête d’authentification est invalide.",
                    "request_id": getattr(request.state, "request_id", ""),
                    "fields": fields,
                }
            },
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(google_places_router)
    app.include_router(maps_router)

    frontend_dist = Path(__file__).resolve().parents[2] / "client" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return app


async def _add_request_id(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    from uuid import uuid4

    request_id = uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
