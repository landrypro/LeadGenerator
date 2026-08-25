from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final
from urllib.parse import urlsplit

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)
VALID_APP_ENVIRONMENTS: Final = frozenset({"development", "test", "staging", "production"})
POSTGRESQL_ASYNC_PREFIX: Final = "postgresql+asyncpg://"
REDIS_PREFIXES: Final = ("redis://", "rediss://")


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str = "development"
    database_url: str = field(default="", repr=False)
    redis_url: str = field(default="", repr=False)
    dependency_connect_timeout_seconds: float = 2.0
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout_seconds: float = 10.0
    database_statement_timeout_ms: int = 15_000
    redis_max_connections: int = 20
    public_app_url: str = ""
    session_cookie_name: str = "prospect_session"
    session_cookie_secure: bool = False
    session_idle_seconds: int = 1_800
    session_absolute_seconds: int = 43_200
    invitation_ttl_seconds: int = 259_200
    invitation_delivery_backend: str = "disabled"
    invitation_from_email: str = "no-reply@marketteo.local"
    invitation_smtp_host: str = "127.0.0.1"
    invitation_smtp_port: int = 1025
    invitation_smtp_timeout_seconds: float = 5.0
    invitation_attempt_window_seconds: int = 900
    invitation_attempt_address_max: int = 30
    invitation_attempt_token_max: int = 10
    invitation_resend_cooldown_seconds: int = 60
    invitation_resend_window_seconds: int = 86_400
    invitation_resend_max_per_window: int = 5
    rate_limit_hmac_key: str = field(default="", repr=False)
    login_rate_limit_window_seconds: int = 900
    login_rate_limit_pair_failures: int = 5
    login_rate_limit_address_failures: int = 20
    google_maps_api_key: str = field(default="", repr=False)
    google_maps_static_api_key: str = field(default="", repr=False)
    cors_allowed_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    places_timeout_seconds: float = 30.0
    static_maps_timeout_seconds: float = 20.0
    map_grant_ttl_seconds: float = 300.0
    map_grant_max_entries: int = 1_000
    google_selection_grant_ttl_seconds: int = 600
    google_selection_grant_max_entries: int = 1_000
    app_title: str = "Marketteo CRM"
    app_version: str = "1.5.0"

    def __post_init__(self) -> None:
        if self.app_env not in VALID_APP_ENVIRONMENTS:
            raise ValueError("APP_ENV doit être development, test, staging ou production.")
        if self.database_url and not self.database_url.startswith(POSTGRESQL_ASYNC_PREFIX):
            raise ValueError("DATABASE_URL doit utiliser postgresql+asyncpg://.")
        if self.redis_url and not self.redis_url.startswith(REDIS_PREFIXES):
            raise ValueError("REDIS_URL doit utiliser redis:// ou rediss://.")
        if self.dependency_connect_timeout_seconds <= 0 or self.database_pool_timeout_seconds <= 0:
            raise ValueError("Les délais des dépendances doivent être positifs.")
        if self.database_pool_size <= 0 or self.database_max_overflow < 0:
            raise ValueError("La configuration du pool PostgreSQL est invalide.")
        if self.database_statement_timeout_ms <= 0 or self.redis_max_connections <= 0:
            raise ValueError("Les limites PostgreSQL et Redis doivent être positives.")
        if not self.session_cookie_name or any(character.isspace() for character in self.session_cookie_name):
            raise ValueError("SESSION_COOKIE_NAME est invalide.")
        if self.session_idle_seconds <= 0 or self.session_absolute_seconds <= self.session_idle_seconds:
            raise ValueError("Les expirations de session sont invalides.")
        if self.invitation_ttl_seconds <= 0 or self.login_rate_limit_window_seconds <= 0:
            raise ValueError("Les durées d’identité doivent être positives.")
        if self.login_rate_limit_pair_failures <= 0 or self.login_rate_limit_address_failures <= 0:
            raise ValueError("Les seuils de connexion doivent être positifs.")
        if self.invitation_delivery_backend not in {"disabled", "mailpit"}:
            raise ValueError("INVITATION_DELIVERY_BACKEND doit être disabled ou mailpit.")
        if self.invitation_delivery_backend == "mailpit" and self.app_env not in {"development", "test"}:
            raise ValueError("Mailpit est interdit en staging et production.")
        if self.invitation_delivery_backend != "disabled" and not _is_http_origin(self.public_app_url):
            raise ValueError("PUBLIC_APP_URL doit être une origine HTTP valide pour envoyer des invitations.")
        if not self.invitation_from_email or "@" not in self.invitation_from_email:
            raise ValueError("INVITATION_FROM_EMAIL est invalide.")
        if not self.invitation_smtp_host or not 1 <= self.invitation_smtp_port <= 65_535:
            raise ValueError("La configuration SMTP des invitations est invalide.")
        if self.invitation_smtp_timeout_seconds <= 0:
            raise ValueError("Le délai SMTP doit être positif.")
        invitation_limits = (
            self.invitation_attempt_window_seconds,
            self.invitation_attempt_address_max,
            self.invitation_attempt_token_max,
            self.invitation_resend_cooldown_seconds,
            self.invitation_resend_window_seconds,
            self.invitation_resend_max_per_window,
        )
        if any(value <= 0 for value in invitation_limits):
            raise ValueError("Les limites d’invitation doivent être positives.")
        if self.rate_limit_hmac_key and len(self.rate_limit_hmac_key.encode("utf-8")) < 32:
            raise ValueError("RATE_LIMIT_HMAC_KEY doit contenir au moins 32 octets.")
        if not self.cors_allowed_origins:
            raise ValueError("Au moins une origine CORS doit être configurée.")
        if self.places_timeout_seconds <= 0 or self.static_maps_timeout_seconds <= 0:
            raise ValueError("Les délais d’attente HTTP doivent être positifs.")
        if self.map_grant_ttl_seconds <= 0 or self.map_grant_max_entries <= 0:
            raise ValueError("La configuration des jetons de carte doit être positive.")
        if self.google_selection_grant_ttl_seconds <= 0 or self.google_selection_grant_max_entries <= 0:
            raise ValueError("La configuration des jetons de sélection Google doit être positive.")
        if self.app_env == "production":
            self._validate_production_settings()

    def _validate_production_settings(self) -> None:
        if not self.database_url or not self.redis_url:
            raise ValueError("PostgreSQL et Redis sont obligatoires en production.")
        if not self.google_maps_api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY est obligatoire en production.")
        if self.map_grant_ttl_seconds > 300:
            raise ValueError("MAP_SNAPSHOT_GRANT_TTL_SECONDS ne peut pas dépasser 300 en production.")
        if not self.session_cookie_secure or not self.session_cookie_name.startswith("__Host-"):
            raise ValueError("Le cookie de session de production doit être Secure et utiliser le préfixe __Host-.")
        if not _is_public_https_origin(self.public_app_url):
            raise ValueError("PUBLIC_APP_URL doit être une origine HTTPS publique en production.")
        if not all(_is_public_https_origin(origin) for origin in self.cors_allowed_origins):
            raise ValueError("Les origines CORS de production doivent être explicites et publiques.")
        if self.public_app_url not in self.cors_allowed_origins:
            raise ValueError("PUBLIC_APP_URL doit être présente dans CORS_ALLOWED_ORIGINS.")
        if not self.rate_limit_hmac_key:
            raise ValueError("RATE_LIMIT_HMAC_KEY est obligatoire hors développement local.")

    @property
    def static_maps_api_key(self) -> str:
        return self.google_maps_static_api_key or self.google_maps_api_key

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if environ is None else environ
        app_env = values.get("APP_ENV", "development").strip().lower()
        configured_origins = values.get("CORS_ALLOWED_ORIGINS", "")
        origins = (
            tuple(origin.strip() for origin in configured_origins.split(",") if origin.strip()) or DEFAULT_CORS_ORIGINS
        )
        return cls(
            app_env=app_env,
            database_url=values.get("DATABASE_URL", "").strip(),
            redis_url=values.get("REDIS_URL", "").strip(),
            dependency_connect_timeout_seconds=float(values.get("DEPENDENCY_CONNECT_TIMEOUT_SECONDS", "2")),
            database_pool_size=int(values.get("DATABASE_POOL_SIZE", "5")),
            database_max_overflow=int(values.get("DATABASE_MAX_OVERFLOW", "10")),
            database_pool_timeout_seconds=float(values.get("DATABASE_POOL_TIMEOUT_SECONDS", "10")),
            database_statement_timeout_ms=int(values.get("DATABASE_STATEMENT_TIMEOUT_MS", "15000")),
            redis_max_connections=int(values.get("REDIS_MAX_CONNECTIONS", "20")),
            public_app_url=values.get("PUBLIC_APP_URL", "").strip().rstrip("/"),
            session_cookie_name=values.get(
                "SESSION_COOKIE_NAME",
                "__Host-prospect_session" if app_env == "production" else "prospect_session",
            ).strip(),
            session_cookie_secure=_parse_bool(
                values.get("SESSION_COOKIE_SECURE", "true" if app_env == "production" else "false")
            ),
            session_idle_seconds=int(values.get("SESSION_IDLE_SECONDS", "1800")),
            session_absolute_seconds=int(values.get("SESSION_ABSOLUTE_SECONDS", "43200")),
            invitation_ttl_seconds=int(values.get("INVITATION_TTL_SECONDS", "259200")),
            invitation_delivery_backend=values.get("INVITATION_DELIVERY_BACKEND", "disabled").strip().lower(),
            invitation_from_email=values.get("INVITATION_FROM_EMAIL", "no-reply@marketteo.local").strip(),
            invitation_smtp_host=values.get("INVITATION_SMTP_HOST", "127.0.0.1").strip(),
            invitation_smtp_port=int(values.get("INVITATION_SMTP_PORT", "1025")),
            invitation_smtp_timeout_seconds=float(values.get("INVITATION_SMTP_TIMEOUT_SECONDS", "5")),
            invitation_attempt_window_seconds=int(values.get("INVITATION_ATTEMPT_WINDOW_SECONDS", "900")),
            invitation_attempt_address_max=int(values.get("INVITATION_ATTEMPT_ADDRESS_MAX", "30")),
            invitation_attempt_token_max=int(values.get("INVITATION_ATTEMPT_TOKEN_MAX", "10")),
            invitation_resend_cooldown_seconds=int(values.get("INVITATION_RESEND_COOLDOWN_SECONDS", "60")),
            invitation_resend_window_seconds=int(values.get("INVITATION_RESEND_WINDOW_SECONDS", "86400")),
            invitation_resend_max_per_window=int(values.get("INVITATION_RESEND_MAX_PER_WINDOW", "5")),
            rate_limit_hmac_key=values.get("RATE_LIMIT_HMAC_KEY", "").strip(),
            login_rate_limit_window_seconds=int(values.get("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "900")),
            login_rate_limit_pair_failures=int(values.get("LOGIN_RATE_LIMIT_PAIR_FAILURES", "5")),
            login_rate_limit_address_failures=int(values.get("LOGIN_RATE_LIMIT_ADDRESS_FAILURES", "20")),
            google_maps_api_key=values.get("GOOGLE_MAPS_API_KEY", "").strip(),
            google_maps_static_api_key=values.get("GOOGLE_MAPS_STATIC_API_KEY", "").strip(),
            cors_allowed_origins=origins,
            places_timeout_seconds=float(values.get("GOOGLE_PLACES_TIMEOUT_SECONDS", "30")),
            static_maps_timeout_seconds=float(values.get("GOOGLE_STATIC_MAPS_TIMEOUT_SECONDS", "20")),
            map_grant_ttl_seconds=float(values.get("MAP_SNAPSHOT_GRANT_TTL_SECONDS", "300")),
            map_grant_max_entries=int(values.get("MAP_SNAPSHOT_GRANT_MAX_ENTRIES", "1000")),
            google_selection_grant_ttl_seconds=int(values.get("GOOGLE_SELECTION_GRANT_TTL_SECONDS", "600")),
            google_selection_grant_max_entries=int(values.get("GOOGLE_SELECTION_GRANT_MAX_ENTRIES", "1000")),
        )


def _is_public_https_origin(origin: str) -> bool:
    if origin == "*":
        return False
    try:
        parsed = urlsplit(origin)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme == "https"
        and hostname
        and hostname not in {"localhost", "127.0.0.1", "::1"}
        and parsed.username is None
        and parsed.password is None
        and not parsed.path
        and not parsed.query
        and not parsed.fragment
    )


def _is_http_origin(origin: str) -> bool:
    try:
        parsed = urlsplit(origin)
        _ = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
        and not parsed.path
        and not parsed.query
        and not parsed.fragment
    )


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Valeur booléenne invalide : {value!r}.")
