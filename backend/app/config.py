from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


@dataclass(frozen=True, slots=True)
class Settings:
    google_maps_api_key: str = ""
    google_maps_static_api_key: str = ""
    cors_allowed_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    places_timeout_seconds: float = 30.0
    places_max_retries: int = 3
    places_retry_base_seconds: float = 0.4
    static_maps_timeout_seconds: float = 20.0
    map_grant_ttl_seconds: float = 300.0
    map_grant_max_entries: int = 1_000
    app_title: str = "Google Maps Lead Generator"
    app_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not self.cors_allowed_origins:
            raise ValueError("Au moins une origine CORS doit être configurée.")
        if self.places_timeout_seconds <= 0 or self.static_maps_timeout_seconds <= 0:
            raise ValueError("Les délais d’attente HTTP doivent être positifs.")
        if self.places_max_retries < 0 or self.places_retry_base_seconds < 0:
            raise ValueError("La configuration des nouvelles tentatives Google est invalide.")
        if self.map_grant_ttl_seconds <= 0 or self.map_grant_max_entries <= 0:
            raise ValueError("La configuration des jetons de carte doit être positive.")

    @property
    def static_maps_api_key(self) -> str:
        return self.google_maps_static_api_key or self.google_maps_api_key

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if environ is None else environ
        configured_origins = values.get("CORS_ALLOWED_ORIGINS", "")
        origins = tuple(
            origin.strip()
            for origin in configured_origins.split(",")
            if origin.strip()
        ) or DEFAULT_CORS_ORIGINS
        return cls(
            google_maps_api_key=values.get("GOOGLE_MAPS_API_KEY", "").strip(),
            google_maps_static_api_key=values.get("GOOGLE_MAPS_STATIC_API_KEY", "").strip(),
            cors_allowed_origins=origins,
            places_timeout_seconds=float(values.get("GOOGLE_PLACES_TIMEOUT_SECONDS", "30")),
            places_max_retries=int(values.get("GOOGLE_PLACES_MAX_RETRIES", "3")),
            places_retry_base_seconds=float(values.get("GOOGLE_PLACES_RETRY_BASE_SECONDS", "0.4")),
            static_maps_timeout_seconds=float(values.get("GOOGLE_STATIC_MAPS_TIMEOUT_SECONDS", "20")),
            map_grant_ttl_seconds=float(values.get("MAP_SNAPSHOT_GRANT_TTL_SECONDS", "300")),
            map_grant_max_entries=int(values.get("MAP_SNAPSHOT_GRANT_MAX_ENTRIES", "1000")),
        )
