from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import AuthenticationServiceUnavailable, InvalidCredentials, LoginRateLimited
from backend.app.application.use_cases import LoginOutcome
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.identity import (
    AuthenticatedIdentity,
    CreatedSession,
    PlatformRole,
    SessionRecord,
    UserIdentity,
    UserStatus,
)

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)


def identity() -> AuthenticatedIdentity:
    user = UserIdentity(
        id=uuid4(),
        email="admin@example.ca",
        display_name="Administrateur",
        password_hash="never-serialized",
        status=UserStatus.ACTIVE,
        platform_role=PlatformRole.PLATFORM_ADMIN,
        last_active_organization_id=None,
        version=1,
        memberships=(),
    )
    return AuthenticatedIdentity(user=user, active_membership=None, csrf_token="csrf-response-token")


class SuccessfulLogin:
    def __init__(self, authenticated_identity: AuthenticatedIdentity) -> None:
        self.identity = authenticated_identity

    async def execute(self, *, email: str, password: str, client_address: str) -> LoginOutcome:
        del email, password, client_address
        record = SessionRecord(
            self.identity.user.id,
            None,
            NOW,
            NOW,
            NOW + timedelta(hours=12),
            self.identity.csrf_token,
            1,
        )
        return LoginOutcome(self.identity, CreatedSession("opaque-cookie-secret", record))


class FailedLogin:
    async def execute(self, *, email: str, password: str, client_address: str) -> LoginOutcome:
        del email, password, client_address
        raise InvalidCredentials


class UnavailableLogin:
    async def execute(self, *, email: str, password: str, client_address: str) -> LoginOutcome:
        del email, password, client_address
        raise AuthenticationServiceUnavailable


class LimitedLogin:
    async def execute(self, *, email: str, password: str, client_address: str) -> LoginOutcome:
        del email, password, client_address
        raise LoginRateLimited(73)


class CurrentSession:
    def __init__(self, authenticated_identity: AuthenticatedIdentity) -> None:
        self.identity = authenticated_identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "opaque-cookie-secret"
        return self.identity


class SuccessfulLogout:
    def __init__(self) -> None:
        self.called = False

    async def execute(self, *, token: str, csrf_token: str) -> None:
        assert token == "opaque-cookie-secret"
        assert csrf_token == "csrf-response-token"
        self.called = True


def auth_app(settings: Settings, login: object) -> tuple[object, SuccessfulLogout]:
    authenticated_identity = identity()
    logout = SuccessfulLogout()
    container = AppContainer(
        settings=settings,
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        login=login,  # type: ignore[arg-type]
        get_current_session=CurrentSession(authenticated_identity),  # type: ignore[arg-type]
        logout=logout,  # type: ignore[arg-type]
    )
    return create_app(container=container), logout


async def test_login_me_and_logout_use_secure_session_contract() -> None:
    authenticated_identity = identity()
    settings = Settings(cors_allowed_origins=("http://test",))
    app, logout = auth_app(settings, SuccessfulLogin(authenticated_identity))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "admin@example.ca", "password": "mot-de-passe-confidentiel"},
            headers={"Origin": "http://test"},
        )
        me_response = await client.get("/api/auth/me")
        logout_response = await client.post(
            "/api/auth/logout",
            json={},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-response-token"},
        )

    assert login_response.status_code == 200
    assert login_response.headers["cache-control"] == "no-store, max-age=0"
    assert "HttpOnly" in login_response.headers["set-cookie"]
    assert "SameSite=lax" in login_response.headers["set-cookie"]
    assert "Path=/" in login_response.headers["set-cookie"]
    assert "Domain=" not in login_response.headers["set-cookie"]
    assert "Secure" not in login_response.headers["set-cookie"]
    assert "opaque-cookie-secret" not in login_response.text
    assert "password" not in login_response.text
    assert me_response.status_code == 200
    assert me_response.json()["user"]["email"] == "admin@example.ca"
    assert me_response.json()["csrf_token"] == "csrf-response-token"
    assert logout_response.status_code == 204
    assert logout.called
    assert "Max-Age=0" in logout_response.headers["set-cookie"]


async def test_login_failure_is_generic_and_contains_request_id_without_credentials() -> None:
    settings = Settings(cors_allowed_origins=("http://test",))
    app, _ = auth_app(settings, FailedLogin())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": "secret@example.ca", "password": "mot-de-passe-secret"},
            headers={"Origin": "http://test"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Courriel ou mot de passe incorrect."
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert "secret@example.ca" not in response.text
    assert "mot-de-passe-secret" not in response.text
    assert response.headers["cache-control"] == "no-store, max-age=0"


async def test_login_rejects_untrusted_origin_and_production_cookie_is_secure() -> None:
    production_settings = Settings(
        app_env="production",
        database_url="postgresql+asyncpg://app:secret@db/prospect",
        redis_url="rediss://redis:6379/0",
        public_app_url="https://crm.example",
        session_cookie_name="__Host-prospect_session",
        session_cookie_secure=True,
        google_maps_api_key="key",
        rate_limit_hmac_key="test-rate-limit-key-with-at-least-32-bytes",
        cors_allowed_origins=("https://crm.example",),
    )
    authenticated_identity = identity()
    app, _ = auth_app(production_settings, SuccessfulLogin(authenticated_identity))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://crm.example") as client:
        rejected = await client.post(
            "/api/auth/login",
            json={"email": "admin@example.ca", "password": "mot-de-passe-confidentiel"},
            headers={"Origin": "https://attacker.example"},
        )
        accepted = await client.post(
            "/api/auth/login",
            json={"email": "admin@example.ca", "password": "mot-de-passe-confidentiel"},
            headers={"Origin": "https://crm.example"},
        )

    assert rejected.status_code == 403
    assert accepted.status_code == 200
    assert accepted.headers["set-cookie"].startswith("__Host-prospect_session=")
    assert "Secure" in accepted.headers["set-cookie"]


async def test_authentication_fails_closed_with_503_and_rate_limit_exposes_retry_after() -> None:
    settings = Settings(cors_allowed_origins=("http://test",))
    unavailable_app, _ = auth_app(settings, UnavailableLogin())
    limited_app, _ = auth_app(settings, LimitedLogin())

    async with AsyncClient(transport=ASGITransport(app=unavailable_app), base_url="http://test") as client:
        unavailable = await client.post(
            "/api/auth/login",
            json={"email": "admin@example.ca", "password": "mot-de-passe-confidentiel"},
            headers={"Origin": "http://test"},
        )
    async with AsyncClient(transport=ASGITransport(app=limited_app), base_url="http://test") as client:
        limited = await client.post(
            "/api/auth/login",
            json={"email": "admin@example.ca", "password": "mot-de-passe-confidentiel"},
            headers={"Origin": "http://test"},
        )
    unconfigured_app = create_app(Settings())
    async with AsyncClient(transport=ASGITransport(app=unconfigured_app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "opaque-cookie-secret")
        unconfigured_me = await client.get("/api/auth/me")

    assert unavailable.status_code == 503
    assert unconfigured_me.status_code == 503
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "73"


async def test_login_validation_never_echoes_an_invalid_password() -> None:
    settings = Settings(cors_allowed_origins=("http://test",))
    app, _ = auth_app(settings, SuccessfulLogin(identity()))
    oversized_password = "secret-ne-doit-jamais-etre-retourne" * 10

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": "admin@example.ca", "password": oversized_password},
            headers={"Origin": "http://test"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert oversized_password not in response.text
    assert response.headers["cache-control"] == "no-store, max-age=0"
