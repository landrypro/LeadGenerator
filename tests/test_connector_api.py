from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.identity import (
    AuthenticatedIdentity,
    MembershipIdentity,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    UserIdentity,
    UserStatus,
)


class CurrentSession:
    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "connector-session"
        return identity()


class ConnectorManagement:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def list(self, context: object) -> tuple[dict[str, object], ...]:
        self.calls.append(("list", context))
        return ()

    async def create(self, context: object, membership_id: UUID, **payload: object) -> dict[str, object]:
        self.calls.append(("create", payload))
        return {"id": uuid4(), "binding_id": uuid4(), "status": "draft", "version": 1}


def identity() -> AuthenticatedIdentity:
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=uuid4(),
        organization_name="QA",
        role=MembershipRole.ADMIN,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=datetime.now(UTC),
    )
    return AuthenticatedIdentity(
        user=UserIdentity(
            id=uuid4(),
            email="admin@example.test",
            display_name="Admin",
            password_hash="hash",
            status=UserStatus.ACTIVE,
            platform_role=None,
            last_active_organization_id=membership.organization_id,
            version=1,
            memberships=(membership,),
        ),
        active_membership=membership,
        csrf_token="connector-csrf",
    )


async def test_meta_connector_routes_are_authenticated_csrf_protected_and_no_store() -> None:
    settings = Settings(cors_allowed_origins=("http://test",), meta_reference_hmac_key="h" * 32)
    management = ConnectorManagement()
    container = AppContainer(
        settings=settings,
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=CurrentSession(),  # type: ignore[arg-type]
        meta_connector_management=management,  # type: ignore[arg-type]
    )
    app = create_app(container=container)
    payload = {
        "provider_id": str(uuid4()),
        "acquisition_id": str(uuid4()),
        "form_id": "form-123",
        "requested_permissions": ["full_name"],
        "allow_full_name": True,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/provider-connectors", json=payload)
        assert response.status_code == 401
        client.cookies.set(settings.session_cookie_name, "connector-session")
        response = await client.post("/api/provider-connectors", json=payload, headers={"Origin": "http://test"})
        assert response.status_code == 403
        response = await client.post(
            "/api/provider-connectors",
            json=payload,
            headers={"Origin": "http://test", "X-CSRF-Token": "connector-csrf"},
        )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert management.calls[-1][0] == "create"
