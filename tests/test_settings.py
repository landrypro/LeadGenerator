import pytest

from backend.app.config import DEFAULT_CORS_ORIGINS, Settings


def test_settings_load_and_normalize_environment_values() -> None:
    settings = Settings.from_env(
        {
            "GOOGLE_MAPS_API_KEY": "  places-key  ",
            "GOOGLE_MAPS_STATIC_API_KEY": " static-key ",
            "CORS_ALLOWED_ORIGINS": "https://crm.example, https://admin.example ",
            "GOOGLE_PLACES_MAX_RETRIES": "5",
            "MAP_SNAPSHOT_GRANT_MAX_ENTRIES": "250",
        }
    )

    assert settings.google_maps_api_key == "places-key"
    assert settings.static_maps_api_key == "static-key"
    assert settings.cors_allowed_origins == ("https://crm.example", "https://admin.example")
    assert settings.places_max_retries == 5
    assert settings.map_grant_max_entries == 250


def test_settings_keep_legacy_defaults_and_static_key_fallback() -> None:
    settings = Settings.from_env({"GOOGLE_MAPS_API_KEY": "shared-key"})

    assert settings.cors_allowed_origins == DEFAULT_CORS_ORIGINS
    assert settings.static_maps_api_key == "shared-key"


def test_settings_reject_invalid_operational_limits() -> None:
    with pytest.raises(ValueError):
        Settings(map_grant_ttl_seconds=0)
