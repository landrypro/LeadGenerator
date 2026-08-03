import pytest

from backend.app.config import DEFAULT_CORS_ORIGINS, Settings


def test_settings_load_and_normalize_environment_values() -> None:
    settings = Settings.from_env(
        {
            "GOOGLE_MAPS_API_KEY": "  places-key  ",
            "GOOGLE_MAPS_STATIC_API_KEY": " static-key ",
            "CORS_ALLOWED_ORIGINS": "https://crm.example, https://admin.example ",
            "DATABASE_URL": "postgresql+asyncpg://app:secret@db/prospect",
            "REDIS_URL": "redis://redis:6379/0",
            "DATABASE_STATEMENT_TIMEOUT_MS": "5000",
            "REDIS_MAX_CONNECTIONS": "12",
            "MAP_SNAPSHOT_GRANT_MAX_ENTRIES": "250",
            "PUBLIC_APP_URL": "https://crm.example/",
            "SESSION_IDLE_SECONDS": "1200",
            "SESSION_ABSOLUTE_SECONDS": "21600",
            "LOGIN_RATE_LIMIT_PAIR_FAILURES": "4",
        }
    )

    assert settings.google_maps_api_key == "places-key"
    assert settings.static_maps_api_key == "static-key"
    assert settings.cors_allowed_origins == ("https://crm.example", "https://admin.example")
    assert settings.database_url == "postgresql+asyncpg://app:secret@db/prospect"
    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.database_statement_timeout_ms == 5_000
    assert settings.redis_max_connections == 12
    assert settings.map_grant_max_entries == 250
    assert settings.public_app_url == "https://crm.example"
    assert settings.session_idle_seconds == 1_200
    assert settings.session_absolute_seconds == 21_600
    assert settings.login_rate_limit_pair_failures == 4


def test_settings_keep_legacy_defaults_and_static_key_fallback() -> None:
    settings = Settings.from_env({"GOOGLE_MAPS_API_KEY": "shared-key"})

    assert settings.cors_allowed_origins == DEFAULT_CORS_ORIGINS
    assert settings.static_maps_api_key == "shared-key"


def test_settings_reject_invalid_operational_limits() -> None:
    with pytest.raises(ValueError):
        Settings(map_grant_ttl_seconds=0)
    with pytest.raises(ValueError):
        Settings(database_statement_timeout_ms=0)
    with pytest.raises(ValueError):
        Settings(redis_max_connections=0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("database_url", "postgresql://db/prospect"),
        ("redis_url", "http://redis:6379"),
    ],
)
def test_settings_reject_unsupported_dependency_urls(field: str, value: str) -> None:
    with pytest.raises(ValueError):
        Settings(**{field: value})  # type: ignore[arg-type]


def test_production_requires_dependencies_google_and_public_cors() -> None:
    with pytest.raises(ValueError, match="PostgreSQL et Redis"):
        Settings(app_env="production", cors_allowed_origins=("https://crm.example",))

    with pytest.raises(ValueError, match="GOOGLE_MAPS_API_KEY"):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://app:secret@db/prospect",
            redis_url="rediss://redis:6379/0",
            cors_allowed_origins=("https://crm.example",),
        )

    with pytest.raises(ValueError, match="CORS"):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://app:secret@db/prospect",
            redis_url="rediss://redis:6379/0",
            google_maps_api_key="key",
            public_app_url="https://crm.example",
            session_cookie_name="__Host-prospect_session",
            session_cookie_secure=True,
        )


def test_settings_repr_redacts_all_credentials() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://app:database-secret@db/prospect",
        redis_url="redis://:redis-secret@redis:6379/0",
        google_maps_api_key="google-secret",
        google_maps_static_api_key="static-secret",
    )

    rendered = repr(settings)

    assert "database-secret" not in rendered
    assert "redis-secret" not in rendered
    assert "google-secret" not in rendered
    assert "static-secret" not in rendered


@pytest.mark.parametrize(
    "origin",
    [
        "http://crm.example",
        "https://LOCALHOST",
        "https://127.0.0.1",
        "https://user:password@crm.example",
        "https://crm.example/path",
        "*",
    ],
)
def test_production_rejects_non_public_cors_origins(origin: str) -> None:
    with pytest.raises(ValueError, match="CORS"):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://app:secret@db/prospect",
            redis_url="rediss://redis:6379/0",
            google_maps_api_key="key",
            public_app_url="https://crm.example",
            session_cookie_name="__Host-prospect_session",
            session_cookie_secure=True,
            cors_allowed_origins=(origin,),
        )


def test_production_requires_secure_host_cookie_and_matching_public_origin() -> None:
    common = {
        "app_env": "production",
        "database_url": "postgresql+asyncpg://app:secret@db/prospect",
        "redis_url": "rediss://redis:6379/0",
        "google_maps_api_key": "key",
        "public_app_url": "https://crm.example",
        "cors_allowed_origins": ("https://crm.example",),
    }

    with pytest.raises(ValueError, match="cookie"):
        Settings(**common)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="PUBLIC_APP_URL"):
        Settings(
            **{**common, "public_app_url": "https://other.example"},  # type: ignore[arg-type]
            session_cookie_name="__Host-prospect_session",
            session_cookie_secure=True,
        )


def test_production_caps_map_grant_lifetime_at_five_minutes() -> None:
    with pytest.raises(ValueError, match="300"):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://app:secret@db/prospect",
            redis_url="rediss://redis:6379/0",
            google_maps_api_key="key",
            public_app_url="https://crm.example",
            session_cookie_name="__Host-prospect_session",
            session_cookie_secure=True,
            cors_allowed_origins=("https://crm.example",),
            rate_limit_hmac_key="a-secret-rate-limit-key-with-at-least-32-bytes",
            map_grant_ttl_seconds=301,
        )


def test_mailpit_is_local_only_and_requires_a_public_app_origin() -> None:
    with pytest.raises(ValueError, match="PUBLIC_APP_URL"):
        Settings(app_env="development", invitation_delivery_backend="mailpit")
    with pytest.raises(ValueError, match="Mailpit"):
        Settings(
            app_env="staging",
            invitation_delivery_backend="mailpit",
            public_app_url="https://crm.example",
            rate_limit_hmac_key="test-rate-limit-key-with-at-least-32-bytes",
        )

    settings = Settings(
        app_env="development",
        invitation_delivery_backend="mailpit",
        public_app_url="http://localhost:5173",
    )
    assert settings.invitation_delivery_backend == "mailpit"


def test_rate_limit_hmac_key_is_redacted_bounded_and_mandatory_in_production() -> None:
    with pytest.raises(ValueError, match="32 octets"):
        Settings(rate_limit_hmac_key="too-short")
    with pytest.raises(ValueError, match="RATE_LIMIT_HMAC_KEY"):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://app:secret@db/prospect",
            redis_url="rediss://redis:6379/0",
            google_maps_api_key="key",
            public_app_url="https://crm.example",
            session_cookie_name="__Host-prospect_session",
            session_cookie_secure=True,
            cors_allowed_origins=("https://crm.example",),
        )

    secret = "a-secret-rate-limit-key-with-at-least-32-bytes"
    assert secret not in repr(Settings(rate_limit_hmac_key=secret))
