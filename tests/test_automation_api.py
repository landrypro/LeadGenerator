from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.ports.assistant import AssistantQuotaReservation, AssistantScopeSnapshot
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.assistant import CreateAssistantPlanUseCase
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.assistant import AssistantPlanItem
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
        return AssistantScopeSnapshot(
            7,
            True,
            items=(
                AssistantPlanItem(
                    id=uuid4(),
                    kind="prospect",
                    label="Atelier Alpha",
                    stage="new",
                    priority=3,
                    updated_at=datetime(2026, 10, 3, 11, tzinfo=UTC),
                ),
            ),
        )


class CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "assistant-session"
        return self.identity


class AutomationSettings:
    def __init__(self, *, enabled: bool) -> None:
        self._enabled = enabled

    async def get(self, *, context: TenantContext) -> SimpleNamespace:
        del context
        return SimpleNamespace(automation_enabled=self._enabled)


def app(
    *,
    role: MembershipRole = MembershipRole.SALES,
    locale: str = "fr-CA",
    rollout_mode: str = "all",
    pilot_organization_ids: tuple[str, ...] | None = None,
    assistant_enabled: bool = True,
    organization_automation_enabled: bool = True,
) -> object:
    organization_id, user_id = uuid4(), uuid4()
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=organization_id,
        organization_name="QA",
        role=role,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=datetime(2026, 10, 1, tzinfo=UTC),
        organization_locale=locale,  # type: ignore[arg-type]
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
        global_enabled=assistant_enabled,
        max_text_characters=500,
        maximum_scope=50,
        timeout_seconds=2,
    )
    pilot_ids = pilot_organization_ids
    if pilot_ids is None and rollout_mode == "pilot":
        pilot_ids = (str(organization_id),)
    container = AppContainer(
        settings=Settings(
            cors_allowed_origins=("http://test",),
            automation_enabled=True,
            automation_assistant_enabled=assistant_enabled,
            automation_rollout_mode=rollout_mode,
            automation_pilot_organization_ids=pilot_ids or (),
        ),
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=CurrentSession(identity),  # type: ignore[arg-type]
        create_assistant_plan=use_case,
        automation_settings=AutomationSettings(enabled=organization_automation_enabled),  # type: ignore[arg-type]
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
    assert success.json()["plan"]["bounded_count"] == 5
    assert success.json()["plan"]["next_cursor"] is None
    assert success.json()["plan"]["items"] == [
        {
            "id": success.json()["plan"]["items"][0]["id"],
            "kind": "prospect",
            "label": "Atelier Alpha",
            "stage": "new",
            "priority": 3,
            "updated_at": "2026-10-03T11:00:00+00:00",
        }
    ]


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


async def test_assistant_suggestions_are_authenticated_and_capability_filtered() -> None:
    async with AsyncClient(transport=ASGITransport(app=app()), base_url="http://test") as client:
        anonymous = await client.get("/api/automation/suggestions")
        client.cookies.set("prospect_session", "assistant-session")
        sales = await client.get("/api/automation/suggestions")

    assert anonymous.status_code == 401
    assert sales.status_code == 200
    assert sales.headers["cache-control"] == "no-store, max-age=0"
    assert [item["code"] for item in sales.json()["items"]] == [
        "scope_open_prospects",
        "prepare_new_prospect_followup",
        "explain_automation_status",
    ]
    assert all(item["code"] != "rebalance_open_prospects" for item in sales.json()["items"])
    assert sales.json()["items"][0]["label"] == "Prospects ouverts"
    assert sales.json()["items"][0]["prompt"] == "Montre-moi les prospects ouverts"


async def test_assistant_suggestions_use_organization_locale_and_admin_scope() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app(role=MembershipRole.ADMIN, locale="en-CA")),
        base_url="http://test",
    ) as client:
        client.cookies.set("prospect_session", "assistant-session")
        response = await client.get("/api/automation/suggestions")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["code"] for item in items] == [
        "scope_open_prospects",
        "rebalance_open_prospects",
        "prepare_new_prospect_followup",
        "explain_automation_status",
    ]
    rebalance = next(item for item in items if item["code"] == "rebalance_open_prospects")
    assert rebalance["label"] == "Review the workload balance"
    assert rebalance["prompt"] == "Review the open prospects workload among my team"
    assert rebalance["required_capability"] == "automation:read:organization"


async def test_every_catalog_suggestion_code_is_accepted_by_guided_plan() -> None:
    async with AsyncClient(transport=ASGITransport(app=app()), base_url="http://test") as client:
        client.cookies.set("prospect_session", "assistant-session")
        suggestions = await client.get("/api/automation/suggestions")
        status_plan = await client.post(
            "/api/automation/intent-plans",
            json={
                "schema_version": 1,
                "input_mode": "guided",
                "user_text": None,
                "suggestion_code": "explain_automation_status",
            },
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf"},
        )

    assert "explain_automation_status" in [item["code"] for item in suggestions.json()["items"]]
    assert status_plan.status_code == 200


async def test_assistant_suggestions_and_availability_require_effective_assistant_enablement() -> None:
    disabled_assistant = app(assistant_enabled=False)
    disabled_organization = app(organization_automation_enabled=False)

    async with AsyncClient(transport=ASGITransport(app=disabled_assistant), base_url="http://test") as client:
        client.cookies.set("prospect_session", "assistant-session")
        unavailable_suggestions = await client.get("/api/automation/suggestions")
        unavailable_availability = await client.get("/api/automation/availability")

    async with AsyncClient(transport=ASGITransport(app=disabled_organization), base_url="http://test") as client:
        client.cookies.set("prospect_session", "assistant-session")
        organization_suggestions = await client.get("/api/automation/suggestions")
        organization_availability = await client.get("/api/automation/availability")

    assert unavailable_suggestions.status_code == 409
    assert unavailable_suggestions.json()["error"]["code"] == "automation_assistant_disabled"
    assert unavailable_availability.json()["assistant_available"] is False
    assert organization_suggestions.status_code == 409
    assert organization_suggestions.json()["error"]["code"] == "automation_assistant_disabled"
    assert organization_availability.json()["assistant_available"] is False


async def test_assistant_rollout_blocks_nonpilot_and_allows_pilot() -> None:
    nonpilot_application = app(rollout_mode="pilot", pilot_organization_ids=(str(uuid4()),))
    async with AsyncClient(transport=ASGITransport(app=nonpilot_application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "assistant-session")
        suggestions = await client.get("/api/automation/suggestions")
        plan = await client.post(
            "/api/automation/intent-plans",
            json={
                "schema_version": 1,
                "input_mode": "guided",
                "user_text": None,
                "suggestion_code": "scope_open_prospects",
            },
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf"},
        )

    pilot_application = app(rollout_mode="pilot")
    async with AsyncClient(transport=ASGITransport(app=pilot_application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "assistant-session")
        pilot_suggestions = await client.get("/api/automation/suggestions")
        pilot_plan = await client.post(
            "/api/automation/intent-plans",
            json={
                "schema_version": 1,
                "input_mode": "guided",
                "user_text": None,
                "suggestion_code": "scope_open_prospects",
            },
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf"},
        )

    assert suggestions.status_code == 409
    assert suggestions.json()["error"]["code"] == "automation_assistant_disabled"
    assert plan.status_code == 409
    assert plan.json()["error"]["code"] == "automation_assistant_disabled"
    assert pilot_suggestions.status_code == 200
    assert pilot_plan.status_code == 200
