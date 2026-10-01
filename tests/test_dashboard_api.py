from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.dashboard import DashboardQuery, GetDashboardSummaryUseCase
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


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 9, 23, 16, 0, tzinfo=UTC)


class Reader:
    async def owner_user_id(self, context: TenantContext, membership_id: UUID) -> UUID | None:
        return None

    async def read(self, query: DashboardQuery) -> dict[str, list[dict[str, object]]]:
        return {name: [] for name in ("prospects", "tasks", "activities", "stages", "opportunities")}


class CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "dashboard-session"
        return self.identity


def app_for(role: MembershipRole = MembershipRole.SALES) -> object:
    organization_id, user_id = uuid4(), uuid4()
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=organization_id,
        organization_name="QA",
        role=role,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        organization_timezone="America/Toronto",
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
    container = AppContainer(
        settings=Settings(cors_allowed_origins=("http://test",)),
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=CurrentSession(identity),  # type: ignore[arg-type]
        get_dashboard_summary=GetDashboardSummaryUseCase(Reader(), Clock()),
    )
    return create_app(container=container)


async def test_dashboard_api_requires_session_and_denies_collective_sales_scope() -> None:
    async with AsyncClient(transport=ASGITransport(app=app_for()), base_url="http://test") as client:
        unauthenticated = await client.get("/api/dashboard/summary?scope=self&period=day")
        client.cookies.set("prospect_session", "dashboard-session")
        forbidden = await client.get("/api/dashboard/summary?scope=organization&period=day")
        another_owner = await client.get(f"/api/dashboard/summary?scope=owner&period=day&owner_membership_id={uuid4()}")
        personal = await client.get("/api/dashboard/summary?scope=self&period=day")
    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert another_owner.status_code == 403
    assert personal.status_code == 200
    assert personal.headers["cache-control"] == "no-store, max-age=0"
    assert personal.json()["google_usage"]["used"] is None


async def test_dashboard_api_validates_period_and_hides_foreign_owner() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app_for(MembershipRole.MANAGER)), base_url="http://test"
    ) as client:
        client.cookies.set("prospect_session", "dashboard-session")
        mixed = await client.get("/api/dashboard/summary?scope=self&period=month&start_on=2026-09-01&end_on=2026-09-30")
        missing = await client.get("/api/dashboard/summary?scope=owner&period=day")
        foreign = await client.get(f"/api/dashboard/summary?scope=owner&period=day&owner_membership_id={uuid4()}")
    assert mixed.status_code == 422 and "period" in mixed.json()["error"]["fields"]
    assert missing.status_code == 422 and "owner_membership_id" in missing.json()["error"]["fields"]
    assert foreign.status_code == 404
