from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.ports.assistant import AssistantQuotaReservation, AssistantScopeSnapshot
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.assistant import CreateAssistantPlanUseCase
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
from backend.app.infrastructure.assistant.fake import FakeAssistantInterpreter


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 10, 3, 12, tzinfo=UTC)


class Protection:
    async def reserve(self, **_: object) -> AssistantQuotaReservation:
        return AssistantQuotaReservation(True, None, 0)

    async def record_provider_success(self) -> None:
        return None

    async def record_provider_failure(self) -> None:
        return None


class Reader:
    async def organization_enabled(self, context: TenantContext) -> bool:
        del context
        return True

    async def resolve(self, context: TenantContext, **_: object) -> AssistantScopeSnapshot:
        del context
        return AssistantScopeSnapshot(7, True)


class CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "assistant-session"
        return self.identity


def app() -> object:
    organization_id, user_id = uuid4(), uuid4()
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=organization_id,
        organization_name="QA",
        role=MembershipRole.SALES,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=datetime(2026, 10, 1, tzinfo=UTC),
        organization_locale="fr-CA",
    )
    identity = AuthenticatedIdentity(
        user=UserIdentity(
            id=user_id,
            email="sales@example.ca",
            display_name="Vente",
            password_hash="hash",
            status=UserStatus.ACTIVE,
            platform_role=None,
            last_active_organization_id=organization_id,
            version=1,
            memberships=(membership,),
        ),
        active_membership=membership,
        csrf_token="csrf",
    )
    use_case = CreateAssistantPlanUseCase(
        FakeAssistantInterpreter(),
        Protection(),
        Reader(),
        Clock(),
        global_enabled=True,
        max_text_characters=500,
        maximum_scope=50,
        timeout_seconds=2,
    )
    container = AppContainer(
        settings=Settings(cors_allowed_origins=("http://test",)),
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=CurrentSession(identity),  # type: ignore[arg-type]
        create_assistant_plan=use_case,
    )
    return create_app(container=container)


async def test_assistant_api_requires_session_and_csrf_then_returns_no_store_plan() -> None:
    async with AsyncClient(transport=ASGITransport(app=app()), base_url="http://test") as client:
        payload = {
            "schema_version": 1,
            "input_mode": "guided",
            "user_text": None,
            "suggestion_code": "scope_open_prospects",
        }
        anonymous = await client.post("/api/automation/intent-plans", json=payload)
        client.cookies.set("prospect_session", "assistant-session")
        missing_csrf = await client.post("/api/automation/intent-plans", json=payload)
        success = await client.post(
            "/api/automation/intent-plans",
            json=payload,
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf"},
        )

    assert anonymous.status_code == 401
    assert missing_csrf.status_code == 403
    assert success.status_code == 200
    assert success.headers["cache-control"] == "no-store, max-age=0"
    assert success.json()["result_code"] == "plan_ready"
    assert success.json()["plan"]["resolved_count"] == 7


async def test_assistant_api_rejects_unknown_input_fields() -> None:
    async with AsyncClient(transport=ASGITransport(app=app()), base_url="http://test") as client:
        client.cookies.set("prospect_session", "assistant-session")
        response = await client.post(
            "/api/automation/intent-plans",
            json={
                "schema_version": 1,
                "input_mode": "guided",
                "user_text": None,
                "suggestion_code": "scope_open_prospects",
                "tool": "forbidden",
            },
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf"},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
