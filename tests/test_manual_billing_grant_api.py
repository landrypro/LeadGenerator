from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import InsufficientCapability
from backend.app.application.ports.manual_billing_grants import (
    ManualBillingGrantOption,
    ManualBillingGrantView,
)
from backend.app.application.use_cases.platform_billing import (
    PlatformBillingDetail,
    PlatformBillingOrganization,
    PlatformBillingPage,
)
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.billing import ManualBillingGrantReasonCode, ManualBillingGrantState
from backend.app.domain.identity import AuthenticatedIdentity, PlatformRole, UserIdentity, UserStatus

NOW = datetime(2026, 10, 30, 12, tzinfo=UTC)


def _identity(*, platform: bool = True) -> AuthenticatedIdentity:
    user = UserIdentity(
        id=uuid4(),
        email="platform@example.ca",
        display_name="Plateforme",
        password_hash="hash",
        status=UserStatus.ACTIVE,
        platform_role=PlatformRole.PLATFORM_ADMIN if platform else None,
        last_active_organization_id=None,
        version=1,
        memberships=(),
    )
    return AuthenticatedIdentity(user, None, "csrf-manual-grant", NOW)


class _CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "manual-grant-session"
        return self.identity


class _Consultation:
    def __init__(self, organization_id: UUID, option: ManualBillingGrantOption) -> None:
        self.organization_id = organization_id
        self.option = option

    async def list(self, **_: object) -> PlatformBillingPage:
        return PlatformBillingPage((), None)

    async def get(self, **_: object) -> PlatformBillingDetail:
        return PlatformBillingDetail(
            organization=PlatformBillingOrganization(
                id=self.organization_id,
                name="Organisation sandbox",
                organization_status="active",
                plan_code=None,
                version_number=None,
                currency=None,
                subscription_state=None,
                contract_state=None,
                source="none",
                current_period_end=None,
                cancel_at_period_end=False,
                reconciliation_status="not_checked",
            ),
            events=(),
            interventions=(),
        )

    async def list_manual_grant_options(self, **kwargs: object) -> tuple[ManualBillingGrantOption, ...]:
        if not kwargs["has_platform_capability"]:
            raise InsufficientCapability
        return (self.option,)


class _ManualGrants:
    def __init__(self, grant: ManualBillingGrantView) -> None:
        self.grant = grant
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def propose(self, **kwargs: object) -> ManualBillingGrantView:
        self.calls.append(("propose", kwargs))
        return self.grant

    async def approve(self, **kwargs: object) -> ManualBillingGrantView:
        self.calls.append(("approve", kwargs))
        return self.grant

    async def revoke(self, **kwargs: object) -> ManualBillingGrantView:
        self.calls.append(("revoke", kwargs))
        return self.grant


def _grant() -> ManualBillingGrantView:
    return ManualBillingGrantView(
        id=uuid4(),
        organization_id=uuid4(),
        plan_version_id=uuid4(),
        plan_code="starter",
        version_number=4,
        currency="XAF",
        reason_code=ManualBillingGrantReasonCode.SANDBOX_VALIDATION,
        duration_days=31,
        state=ManualBillingGrantState.PENDING_APPROVAL,
        starts_at=None,
        ends_at=None,
        version=1,
    )


def _app(identity: AuthenticatedIdentity, grants: _ManualGrants):
    option = ManualBillingGrantOption(
        plan_version_id=grants.grant.plan_version_id,
        code="starter",
        version_number=4,
        currency="XAF",
        amount_minor=5000,
    )
    return create_app(
        container=AppContainer(
            settings=Settings(cors_allowed_origins=("http://test",)),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            get_current_session=_CurrentSession(identity),  # type: ignore[arg-type]
            platform_billing_consultation=_Consultation(grants.grant.organization_id, option),  # type: ignore[arg-type]
            manual_billing_grants=grants,  # type: ignore[arg-type]
        )
    )


async def test_manual_grant_routes_are_platform_protected_minimized_and_idempotent() -> None:
    grant = _grant()
    grants = _ManualGrants(grant)
    app = _app(_identity(), grants)
    headers = {
        "origin": "http://test",
        "x-csrf-token": "csrf-manual-grant",
        "idempotency-key": "manual-grant-api-key",
    }
    payload = {
        "organization_id": str(grant.organization_id),
        "plan_version_id": str(grant.plan_version_id),
        "reason_code": "sandbox_validation",
        "duration_days": 31,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        anonymous = await client.get("/api/platform/billing/manual-grant-options")
        client.cookies.set("prospect_session", "manual-grant-session")
        options = await client.get("/api/platform/billing/manual-grant-options")
        rejected = await client.post(
            "/api/platform/billing/manual-grants", json=payload, headers={"origin": "http://test"}
        )
        proposed = await client.post("/api/platform/billing/manual-grants", json=payload, headers=headers)
        approved = await client.post(
            f"/api/platform/billing/manual-grants/{grant.id}/approve",
            json={"version": 1},
            headers={**headers, "idempotency-key": "manual-grant-approval-key"},
        )
        revoked = await client.post(
            f"/api/platform/billing/manual-grants/{grant.id}/revoke",
            json={"version": 1},
            headers={**headers, "idempotency-key": "manual-grant-revoke-key"},
        )

    assert anonymous.status_code == 401
    assert options.status_code == 200
    assert options.json() == [
        {
            "plan_version_id": str(grant.plan_version_id),
            "code": "starter",
            "version_number": 4,
            "currency": "XAF",
            "amount_minor": 5000,
        }
    ]
    assert rejected.status_code == 403
    assert proposed.status_code == approved.status_code == revoked.status_code == 200
    assert set(proposed.json()) == {
        "id",
        "organization_id",
        "plan_version_id",
        "plan_code",
        "version_number",
        "currency",
        "reason_code",
        "duration_days",
        "state",
        "starts_at",
        "ends_at",
        "version",
    }
    assert all(forbidden not in proposed.text for forbidden in ("cus_", "sub_", "requested_by", "approved_by"))
    assert [name for name, _ in grants.calls] == ["propose", "approve", "revoke"]
    assert all(call["has_platform_capability"] is True for _, call in grants.calls)
    assert grants.calls[0][1]["idempotency_key"] == "manual-grant-api-key"


async def test_manual_grant_routes_reject_non_platform_users() -> None:
    grants = _ManualGrants(_grant())
    app = _app(_identity(platform=False), grants)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "manual-grant-session")
        response = await client.get("/api/platform/billing/manual-grant-options")

    assert response.status_code == 403
    assert grants.calls == []
