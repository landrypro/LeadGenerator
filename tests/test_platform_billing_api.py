from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import InsufficientCapability
from backend.app.application.use_cases.platform_billing import (
    PlatformBillingDetail,
    PlatformBillingEvent,
    PlatformBillingIntervention,
    PlatformBillingOrganization,
    PlatformBillingPage,
)
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.identity import AuthenticatedIdentity, PlatformRole, UserIdentity, UserStatus

NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)


def _identity(*, platform: bool) -> AuthenticatedIdentity:
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
    return AuthenticatedIdentity(user, None, "csrf", NOW)


class _CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "current-session"
        return self.identity


def _item(organization_id: UUID | None = None) -> PlatformBillingOrganization:
    return PlatformBillingOrganization(
        id=organization_id or uuid4(),
        name="Organisation démonstration",
        organization_status="active",
        plan_code="starter",
        version_number=4,
        currency="XAF",
        subscription_state="active",
        contract_state="active",
        source="stripe",
        current_period_end=NOW,
        cancel_at_period_end=False,
        reconciliation_status="needs_review",
    )


class _Consultation:
    def __init__(self) -> None:
        self.item = _item()
        self.list_calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []

    async def list(self, **kwargs: object) -> PlatformBillingPage:
        if not kwargs["has_platform_capability"]:
            raise InsufficientCapability
        self.list_calls.append(kwargs)
        return PlatformBillingPage((self.item,), str(uuid4()))

    async def get(self, **kwargs: object) -> PlatformBillingDetail:
        if not kwargs["has_platform_capability"]:
            raise InsufficientCapability
        self.get_calls.append(kwargs)
        return PlatformBillingDetail(
            organization=self.item,
            events=(PlatformBillingEvent("invoice.paid", NOW),),
            interventions=(PlatformBillingIntervention("checkout", "succeeded", NOW, NOW),),
        )


def _app(identity: AuthenticatedIdentity, consultation: _Consultation):
    return create_app(
        container=AppContainer(
            settings=Settings(cors_allowed_origins=("http://test",)),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            get_current_session=_CurrentSession(identity),  # type: ignore[arg-type]
            platform_billing_consultation=consultation,  # type: ignore[arg-type]
        )
    )


async def test_platform_billing_consultation_requires_platform_billing_capability() -> None:
    consultation = _Consultation()
    app = _app(_identity(platform=False), consultation)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        anonymous = await client.get("/api/platform/billing/organizations")
        client.cookies.set("prospect_session", "current-session")
        forbidden = await client.get("/api/platform/billing/organizations")

    assert anonymous.status_code == 401
    assert forbidden.status_code == 403
    assert consultation.list_calls == []


async def test_platform_billing_list_is_paginated_filtered_and_hides_provider_references() -> None:
    consultation = _Consultation()
    cursor = str(uuid4())
    app = _app(_identity(platform=True), consultation)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "current-session")
        response = await client.get(
            f"/api/platform/billing/organizations?cursor={cursor}&limit=25&state=active&source=stripe"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert consultation.list_calls[0]["cursor"] == cursor
    assert consultation.list_calls[0]["state"] == "active"
    assert consultation.list_calls[0]["source"] == "stripe"
    assert set(response.json()["items"][0]) == {
        "id",
        "name",
        "organization_status",
        "plan_code",
        "version_number",
        "currency",
        "subscription_state",
        "contract_state",
        "manual_grant_state",
        "source",
        "current_period_end",
        "cancel_at_period_end",
        "reconciliation_status",
    }
    assert all(forbidden not in response.text for forbidden in ("cus_", "sub_", "evt_", "normalized_payload"))


async def test_platform_billing_detail_exposes_only_summarized_events_and_commands() -> None:
    consultation = _Consultation()
    app = _app(_identity(platform=True), consultation)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "current-session")
        response = await client.get(f"/api/platform/billing/organizations/{consultation.item.id}")

    assert response.status_code == 200
    assert response.json()["events"] == [
        {"event_type": "invoice.paid", "occurred_at": NOW.isoformat().replace("+00:00", "Z")}
    ]
    assert response.json()["interventions"][0]["kind"] == "checkout"
    assert all(
        forbidden not in response.text
        for forbidden in ("provider_customer_reference", "provider_subscription_reference", "payload")
    )
