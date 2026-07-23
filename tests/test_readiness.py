from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.application.ports.health import DependencyHealth
from backend.app.application.use_cases import CheckReadinessUseCase
from backend.app.application.use_cases.search_google_places import SearchGooglePlacesOutcome
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.google_place import GooglePlaceSearchResult, GooglePlaceSearchStats


class StubProbe:
    def __init__(self, name: str, state: str) -> None:
        self._name = name
        self._state = state

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> DependencyHealth:
        return DependencyHealth(name=self.name, state=self._state)  # type: ignore[arg-type]


class StubSearch:
    async def execute(self, criteria: object, business_address: str) -> SearchGooglePlacesOutcome:
        del criteria, business_address
        return SearchGooglePlacesOutcome(
            search=GooglePlaceSearchResult(
                places=[],
                stats=GooglePlaceSearchStats(api_calls=1, raw_results=0, displayed_results=0),
                searched_at=datetime.now(UTC),
            ),
            map_snapshot_token="token",
        )


class StubResource:
    def __init__(self, name: str, calls: list[str], *, fails: bool = False) -> None:
        self._name = name
        self._calls = calls
        self._fails = fails

    async def close(self) -> None:
        self._calls.append(self._name)
        if self._fails:
            raise RuntimeError(f"{self._name} unavailable")


async def test_liveness_does_not_depend_on_external_services() -> None:
    app = create_app(Settings())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_reports_missing_postgresql_and_redis() -> None:
    app = create_app(Settings())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": {"postgresql": "not_configured", "redis": "not_configured"},
    }


async def test_readiness_uses_injected_probes_without_leaking_errors() -> None:
    settings = Settings()
    container = AppContainer(
        settings=settings,
        search_google_places=StubSearch(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        readiness=CheckReadinessUseCase(
            (
                StubProbe("postgresql", "ok"),
                StubProbe("redis", "unavailable"),
            )
        ),
    )
    app = create_app(container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": {"postgresql": "ok", "redis": "unavailable"},
    }


async def test_container_attempts_to_close_every_resource_in_reverse_order() -> None:
    calls: list[str] = []
    container = AppContainer(
        settings=Settings(),
        search_google_places=StubSearch(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        resources=(
            StubResource("postgresql", calls),
            StubResource("redis", calls, fails=True),
        ),
    )

    with pytest.raises(ExceptionGroup, match="fermeture"):
        await container.close()

    assert calls == ["redis", "postgresql"]
