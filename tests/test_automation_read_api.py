from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from fastapi import FastAPI
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
from backend.app.infrastructure.postgres.automation_exception_resolution import AutomationExceptionOutcome
from backend.app.infrastructure.postgres.automation_lifecycle import AutomationLifecycleOutcome
from backend.app.infrastructure.postgres.automation_preflight import AutomationPreflightOutcome
from backend.app.infrastructure.postgres.automation_settings import (
    AutomationSettingsVersionConflict,
    AutomationSettingsView,
)


class CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "automation-session"
        return self.identity


class AutomationReader:
    def __init__(self) -> None:
        self.playbook_scopes: list[bool] = []
        self.exception_scopes: list[bool] = []

    async def list_playbooks(self, _context: object, **kwargs: object) -> dict[str, object]:
        self.playbook_scopes.append(bool(kwargs["organization_scope"]))
        return {
            "items": [
                {
                    "id": uuid4(),
                    "code": "new_prospect",
                    "state": "active",
                    "latest_preflight_state": "valid",
                    "created_at": datetime(2026, 10, 5, tzinfo=UTC),
                }
            ],
            "next_cursor": None,
        }

    async def get_playbook(self, _context: object, **kwargs: object) -> dict[str, object] | None:
        if not kwargs["organization_scope"]:
            return None
        return {"id": uuid4(), "code": kwargs["code"], "state": "active"}

    async def list_exceptions(self, _context: object, **kwargs: object) -> dict[str, object]:
        self.exception_scopes.append(bool(kwargs["organization_scope"]))
        return {
            "items": [
                {
                    "id": uuid4(),
                    "exception_code": "owner_unavailable",
                    "state": kwargs["state"] or "open",
                    "assigned_membership_id": kwargs["membership_id"],
                    "created_at": datetime(2026, 10, 5, tzinfo=UTC),
                }
            ],
            "next_cursor": None,
        }

    async def get_exception(self, _context: object, **kwargs: object) -> dict[str, object] | None:
        return {"id": kwargs["exception_id"], "exception_code": "owner_unavailable", "state": "open"}

    async def get_preflight(self, _context: object, **kwargs: object) -> dict[str, object] | None:
        return {"id": kwargs["preflight_id"], "playbook_code": "new_prospect", "state": "valid"}


class PreflightRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def run(self, **kwargs: object) -> AutomationPreflightOutcome:
        self.calls.append(kwargs)
        now = "2026-10-05T12:00:00+00:00"
        return AutomationPreflightOutcome(
            id=uuid4(),
            playbook_code=str(kwargs["playbook_code"]),
            ruleset_version="FEU-1.0",
            state="completed",
            correlation_id=uuid4(),
            subject_count=0,
            green_count=0,
            yellow_count=0,
            red_count=0,
            to_verify_count=0,
            created_at=now,
            updated_at=now,
            expires_at="2026-10-05T12:15:00+00:00",
            replayed=False,
        )


class PlaybookLifecycle:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def transition(self, **kwargs: object) -> AutomationLifecycleOutcome:
        self.calls.append(kwargs)
        command = cast(Literal["activate", "suspend", "resume"], kwargs["command"])
        state = {"activate": "active_prepare", "suspend": "suspended", "resume": "preflight_required"}[command]
        return AutomationLifecycleOutcome(
            playbook_code=str(kwargs["playbook_code"]),
            command=command,
            state=state,
            prepare_enabled=command == "activate",
            suspension_generation=1 if command == "suspend" else 0,
            version=cast(int, kwargs["expected_version"]) + 1,
            correlation_id=uuid4(),
            replayed=False,
        )


class ExceptionResolution:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def transition(self, **kwargs: object) -> AutomationExceptionOutcome:
        self.calls.append(kwargs)
        command = cast(Literal["claim", "resolve", "abandon", "reconcile"], kwargs["command"])
        state = {
            "claim": "in_progress",
            "resolve": "resolved",
            "abandon": "abandoned",
            "reconcile": "in_progress",
        }[command]
        return AutomationExceptionOutcome(
            id=cast(UUID, kwargs["exception_id"]),
            command=command,
            state=state,
            assigned_membership_id=cast(UUID, kwargs["membership_id"]),
            resolution_code=cast(str | None, kwargs["resolution_code"]),
            version=cast(int, kwargs["expected_version"]) + 1,
            correlation_id=uuid4(),
            replayed=False,
        )


class SettingsService:
    def __init__(self, *, organization_id: UUID) -> None:
        self.item = AutomationSettingsView(
            id=uuid4(), organization_id=organization_id, automation_enabled=False,
            suspension_generation=0, version=1, created_at=None, updated_at=None,
        )

    async def get(self, *, context: object) -> AutomationSettingsView:
        del context
        return self.item

    async def update(self, *, context: object, automation_enabled: bool, expected_version: int) -> AutomationSettingsView:
        del context
        if expected_version != self.item.version:
            raise AutomationSettingsVersionConflict(self.item.version)
        self.item = AutomationSettingsView(
            id=self.item.id, organization_id=self.item.organization_id,
            automation_enabled=automation_enabled,
            suspension_generation=self.item.suspension_generation + int(self.item.automation_enabled and not automation_enabled),
            version=self.item.version + int(self.item.automation_enabled != automation_enabled),
            created_at=self.item.created_at, updated_at=self.item.updated_at,
        )
        return self.item


def build_app(
    role: MembershipRole = MembershipRole.SALES,
    *,
    automation_enabled: bool = False,
) -> tuple[FastAPI, AutomationReader, PreflightRunner]:
    organization_id, user_id = uuid4(), uuid4()
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=organization_id,
        organization_name="QA",
        role=role,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=datetime(2026, 10, 1, tzinfo=UTC),
        organization_locale="fr-CA",
    )
    identity = AuthenticatedIdentity(
        user=UserIdentity(
            id=user_id,
            email="automation@example.ca",
            display_name="Automation",
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
    reader = AutomationReader()
    preflight_runner = PreflightRunner()
    lifecycle = PlaybookLifecycle()
    exception_resolution = ExceptionResolution()
    container = AppContainer(
        settings=Settings(
            cors_allowed_origins=("http://test",),
            automation_enabled=automation_enabled,
        ),
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=CurrentSession(identity),  # type: ignore[arg-type]
        automation_reader=reader,  # type: ignore[arg-type]
        automation_preflight_runner=preflight_runner,  # type: ignore[arg-type]
        automation_playbook_lifecycle=lifecycle,  # type: ignore[arg-type]
        automation_exception_resolution=exception_resolution,  # type: ignore[arg-type]
    )
    return create_app(container=container), reader, preflight_runner


async def test_automation_read_requires_session_and_keeps_responses_private() -> None:
    application, _reader, _runner = build_app()
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        anonymous = await client.get("/api/automation/playbooks")
        client.cookies.set("prospect_session", "automation-session")
        response = await client.get("/api/automation/exceptions?state=open")

    assert anonymous.status_code == 401
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["items"][0]["state"] == "open"


async def test_automation_settings_is_admin_only_and_versioned() -> None:
    organization_id, user_id = uuid4(), uuid4()
    membership = MembershipIdentity(
        id=uuid4(), organization_id=organization_id, organization_name="QA", role=MembershipRole.ADMIN,
        status=MembershipStatus.ACTIVE, organization_status=OrganizationStatus.ACTIVE,
        created_at=datetime(2026, 10, 1, tzinfo=UTC), organization_locale="fr-CA",
    )
    identity = AuthenticatedIdentity(
        user=UserIdentity(
            id=user_id, email="automation-admin@example.ca", display_name="Admin", password_hash="hash",
            status=UserStatus.ACTIVE, platform_role=None, last_active_organization_id=organization_id,
            version=1, memberships=(membership,),
        ), active_membership=membership, csrf_token="csrf",
    )
    settings_service = SettingsService(organization_id=organization_id)
    container = AppContainer(
        settings=Settings(cors_allowed_origins=("http://test",), automation_enabled=True),
        search_google_places=object(), get_map_snapshot=object(),
        get_current_session=CurrentSession(identity),  # type: ignore[arg-type]
        automation_settings=settings_service,  # type: ignore[arg-type]
    )
    application = create_app(container=container)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        response = await client.get("/api/automation/settings")
        availability_before = await client.get("/api/automation/availability")
        updated = await client.patch(
            "/api/automation/settings",
            json={"schema_version": 1, "automation_enabled": True, "expected_version": 1},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf"},
        )
        availability_after = await client.get("/api/automation/availability")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["item"]["automation_enabled"] is False
    assert availability_before.status_code == 200
    assert availability_before.json()["effective_enabled"] is False
    assert updated.status_code == 200
    assert updated.headers["etag"] == '"2"'
    assert updated.json()["effective_enabled"] is True
    assert availability_after.status_code == 200
    assert availability_after.json()["effective_enabled"] is True


async def test_automation_read_keeps_sales_in_self_scope_and_admin_in_organization_scope() -> None:
    sales_application, sales_reader, _sales_runner = build_app()
    async with AsyncClient(transport=ASGITransport(app=sales_application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        playbooks = await client.get("/api/automation/playbooks")
        exceptions = await client.get("/api/automation/exceptions")

    admin_application, admin_reader, _admin_runner = build_app(MembershipRole.ADMIN)
    async with AsyncClient(transport=ASGITransport(app=admin_application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        admin_playbooks = await client.get("/api/automation/playbooks")
        admin_exceptions = await client.get("/api/automation/exceptions")

    assert playbooks.status_code == 200
    assert exceptions.status_code == 200
    assert sales_reader.playbook_scopes == [False]
    assert sales_reader.exception_scopes == [False]
    assert admin_playbooks.status_code == 200
    assert admin_exceptions.status_code == 200
    assert admin_reader.playbook_scopes == [True]
    assert admin_reader.exception_scopes == [True]


async def test_preflight_availability_requires_the_capability_and_enabled_environment() -> None:
    sales_application, _sales_reader, _sales_runner = build_app(automation_enabled=True)
    disabled_application, _disabled_reader, _disabled_runner = build_app(MembershipRole.ADMIN)
    enabled_application, _enabled_reader, _enabled_runner = build_app(
        MembershipRole.ADMIN,
        automation_enabled=True,
    )

    async with AsyncClient(transport=ASGITransport(app=sales_application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        sales_response = await client.get("/api/automation/playbooks")
    async with AsyncClient(transport=ASGITransport(app=disabled_application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        disabled_response = await client.get("/api/automation/playbooks")
    async with AsyncClient(transport=ASGITransport(app=enabled_application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        enabled_response = await client.get("/api/automation/playbooks")

    assert sales_response.json()["preflight_enabled"] is False
    assert disabled_response.json()["preflight_enabled"] is False
    assert enabled_response.json()["preflight_enabled"] is True


async def test_automation_read_rejects_invalid_queries_and_hides_unknown_resources() -> None:
    application, _reader, _runner = build_app()
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        invalid_state = await client.get("/api/automation/exceptions?state=unsafe")
        invalid_cursor = await client.get("/api/automation/exceptions?cursor=not-an-id")
        unexpected_query = await client.get(f"/api/automation/preflights/{uuid4()}?limit=1")
        hidden_playbook = await client.get("/api/automation/playbooks/not-a-playbook")
        malformed_resource = await client.get("/api/automation/exceptions/not-an-id")

    assert invalid_state.status_code == 422
    assert invalid_state.json()["error"]["code"] == "automation_query_invalid"
    assert invalid_cursor.status_code == 422
    assert unexpected_query.status_code == 422
    assert hidden_playbook.status_code == 404
    assert malformed_resource.status_code == 422


async def test_preflight_requires_manager_capability_and_creates_only_a_preflight_record() -> None:
    sales_application, _sales_reader, sales_runner = build_app()
    async with AsyncClient(transport=ASGITransport(app=sales_application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        sales_response = await client.post(
            "/api/automation/playbooks/new_prospect/preflights",
            json={"schema_version": 1, "idempotency_key": "preflight-sales"},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf"},
        )

    admin_application, _admin_reader, admin_runner = build_app(MembershipRole.ADMIN)
    async with AsyncClient(transport=ASGITransport(app=admin_application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        admin_response = await client.post(
            "/api/automation/playbooks/new_prospect/preflights",
            json={"schema_version": 1, "idempotency_key": "preflight-admin"},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf"},
        )

    assert sales_response.status_code == 403
    assert sales_runner.calls == []
    assert admin_response.status_code == 201
    assert admin_response.headers["cache-control"] == "no-store, max-age=0"
    assert admin_response.json()["item"]["subject_count"] == 0
    assert len(admin_runner.calls) == 1


async def test_playbook_lifecycle_requires_capability_csrf_and_if_match() -> None:
    sales_application, _sales_reader, _sales_runner = build_app(automation_enabled=True)
    async with AsyncClient(transport=ASGITransport(app=sales_application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        sales_response = await client.post(
            "/api/automation/playbooks/new_prospect/suspend",
            json={"schema_version": 1, "idempotency_key": "suspend-sales", "reason_code": "operator_request"},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf", "If-Match": '"1"'},
        )

    admin_application, _admin_reader, _admin_runner = build_app(MembershipRole.ADMIN, automation_enabled=True)
    async with AsyncClient(transport=ASGITransport(app=admin_application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        invalid_response = await client.post(
            "/api/automation/playbooks/new_prospect/suspend",
            json={"schema_version": 1, "idempotency_key": "suspend-invalid", "reason_code": "operator_request"},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf"},
        )
        suspended_response = await client.post(
            "/api/automation/playbooks/new_prospect/suspend",
            json={"schema_version": 1, "idempotency_key": "suspend-admin", "reason_code": "operator_request"},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf", "If-Match": '"3"'},
        )
        resumed_response = await client.post(
            "/api/automation/playbooks/new_prospect/resume",
            json={"schema_version": 1, "idempotency_key": "resume-admin"},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf", "If-Match": '"4"'},
        )

    assert sales_response.status_code == 403
    assert invalid_response.status_code == 422
    assert suspended_response.status_code == 200
    assert suspended_response.headers["cache-control"] == "no-store, max-age=0"
    assert suspended_response.headers["etag"] == '"4"'
    assert suspended_response.json()["item"]["state"] == "suspended"
    assert resumed_response.status_code == 200
    assert resumed_response.json()["item"]["state"] == "preflight_required"


async def test_exception_commands_are_versioned_and_do_not_require_automation_activation() -> None:
    application, _reader, _preflight_runner = build_app()
    exception_id = uuid4()
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        client.cookies.set("prospect_session", "automation-session")
        claim = await client.post(
            f"/api/automation/exceptions/{exception_id}/claim",
            json={"schema_version": 1, "idempotency_key": "claim-self"},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf", "If-Match": '"1"'},
        )
        resolve = await client.post(
            f"/api/automation/exceptions/{exception_id}/resolve",
            json={
                "schema_version": 1,
                "idempotency_key": "resolve-self",
                "resolution_code": "human_review_complete",
            },
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf", "If-Match": '"2"'},
        )
        invalid_resolution = await client.post(
            f"/api/automation/exceptions/{exception_id}/resolve",
            json={
                "schema_version": 1,
                "idempotency_key": "resolve-invalid",
                "resolution_code": "arbitrary_free_text",
            },
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf", "If-Match": '"3"'},
        )

    assert claim.status_code == 200
    assert claim.json()["item"]["state"] == "in_progress"
    assert claim.headers["etag"] == '"2"'
    assert resolve.status_code == 200
    assert resolve.json()["item"]["state"] == "resolved"
    assert invalid_resolution.status_code == 422
