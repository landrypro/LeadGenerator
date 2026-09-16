import json

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.infrastructure.observability import PrometheusMetricsRecorder, configure_application_logging

METRICS_TOKEN = "metrics-test-token-with-at-least-thirty-two-bytes"


def test_json_logger_uses_a_closed_schema_without_sensitive_fields(capsys: pytest.CaptureFixture[str]) -> None:
    logger = configure_application_logging(log_format="json", instance_id="api-test")

    logger.info(
        "google_search_quota_consumed",
        request_id="request-opaque",
        policy_code="server_default_v1",
        email="person@example.test",  # type: ignore[call-arg]
        place_id="ChIJ-secret",  # type: ignore[call-arg]
    )

    event = json.loads(capsys.readouterr().out)
    assert event["event"] == "google_search_quota_consumed"
    assert event["instance_id"] == "api-test"
    assert event["request_id"] == "request-opaque"
    assert event["policy_code"] == "server_default_v1"
    assert "person@example.test" not in json.dumps(event)
    assert "ChIJ-secret" not in json.dumps(event)


async def test_internal_metrics_are_private_and_emit_only_bounded_labels() -> None:
    recorder = PrometheusMetricsRecorder()
    recorder.record_google_search_lock("accepted")
    recorder.record_google_search_quota("user", "accepted", "server_default_v1")
    settings = Settings(
        app_env="test",
        metrics_enabled=True,
        metrics_bearer_token=METRICS_TOKEN,
        cors_allowed_origins=("http://test",),
    )
    container = AppContainer(
        settings=settings,
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        metrics=recorder,
        metrics_exporter=recorder,
    )
    app = create_app(container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        disabled = await client.get("/internal/metrics")
        authorized = await client.get("/internal/metrics", headers={"Authorization": f"Bearer {METRICS_TOKEN}"})

    assert disabled.status_code == 404
    assert authorized.status_code == 200
    assert authorized.headers["cache-control"] == "no-store, max-age=0"
    assert authorized.headers["x-robots-tag"] == "noindex, nofollow"
    assert 'marketteo_google_search_lock_total{outcome="accepted"} 1' in authorized.text
    assert 'policy_code="server_default_v1"' in authorized.text
    assert "request_id" not in authorized.text
    assert "organization_id" not in authorized.text


async def test_disabled_metrics_are_indistinguishable_from_an_invalid_bearer() -> None:
    settings = Settings(app_env="test", cors_allowed_origins=("http://test",))
    container = AppContainer(
        settings=settings,
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
    )
    app = create_app(container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/internal/metrics", headers={"Authorization": f"Bearer {METRICS_TOKEN}"})

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store, max-age=0"


async def test_unmatched_path_is_normalized_before_json_logging(capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(app_env="test", log_format="json", cors_allowed_origins=("http://test",))
    container = AppContainer(
        settings=settings,
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
    )
    app = create_app(container=container)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/missing/person@example.test")

    assert response.status_code == 200
    event = json.loads(capsys.readouterr().out)
    assert event["route"] == "/{frontend_path:path}"
    assert "person@example.test" not in json.dumps(event)


def test_staging_requires_json_logs_enabled_metrics_and_a_secret() -> None:
    common = {"app_env": "staging", "redis_url": "rediss://redis:6379/0", "log_format": "json"}

    with pytest.raises(ValueError, match="METRICS_ENABLED"):
        Settings(**common)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="32 octets"):
        Settings(**{**common, "metrics_enabled": True, "metrics_bearer_token": "short"})  # type: ignore[arg-type]

    settings = Settings(**{**common, "metrics_enabled": True, "metrics_bearer_token": METRICS_TOKEN})  # type: ignore[arg-type]
    assert settings.metrics_enabled is True
