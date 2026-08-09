from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import InsufficientCapability, InvalidAuditCursor
from backend.app.application.tenancy import ActorContext, TenantContext
from backend.app.application.use_cases.audit import (
    AuditEventPage,
    ListPlatformAuditEventsUseCase,
    ListTenantAuditEventsUseCase,
)
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.audit import (
    AuditActorKind,
    AuditActorView,
    AuditEventView,
    AuditSource,
)
from backend.app.domain.identity import (
    AuthenticatedIdentity,
    MembershipIdentity,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    PlatformRole,
    UserIdentity,
    UserStatus,
)
from backend.app.infrastructure.audit_pagination import HmacAuditCursorCodec

NOW = datetime(2026, 8, 9, 16, tzinfo=UTC)
KEY = b"audit-consultation-test-key-with-at-least-32-bytes"


class FixedClock:
    def now(self) -> datetime:
        return NOW


class Reader:
    def __init__(self, rows: tuple[AuditEventView, ...]) -> None:
        self.rows = rows
        self.calls: list[dict[str, object]] = []

    async def list_events(self, **kwargs) -> tuple[AuditEventView, ...]:
        self.calls.append(kwargs)
        return self.rows


class ReadUnitOfWork:
    def __init__(self, reader: Reader) -> None:
        self.reader = reader

    async def __aenter__(self) -> ReadUnitOfWork:
        return self

    async def __aexit__(self, *args) -> None:
        return None


def event(index: int, *, action: str = "organization.updated") -> AuditEventView:
    return AuditEventView(
        id=UUID(int=index + 1),
        occurred_at=NOW - timedelta(minutes=index),
        action=action,
        entity_type="organization",
        entity_id=UUID(int=100 + index),
        actor=AuditActorView(AuditActorKind.USER, UUID(int=200), "Gestionnaire"),
        request_id=f"request-{index}",
        correlation_id=f"request-{index}",
        source=AuditSource.API,
        metadata={"changed_fields": ["name"]},
        schema_version=1,
    )


async def test_tenant_audit_uses_default_window_and_signed_pagination() -> None:
    reader = Reader((event(0), event(1)))
    context = TenantContext(UUID(int=200), UUID(int=300), "request-list")
    use_case = ListTenantAuditEventsUseCase(lambda _: ReadUnitOfWork(reader), HmacAuditCursorCodec(KEY), FixedClock())

    first = await use_case.execute(context=context, has_capability=True, cursor=None, limit=1)

    assert first.items == (event(0),)
    assert first.occurred_from == NOW - timedelta(days=30)
    assert first.occurred_to == NOW
    assert first.next_cursor
    assert reader.calls[0]["limit"] == 2

    reader.rows = ()
    second = await use_case.execute(
        context=context,
        has_capability=True,
        cursor=first.next_cursor,
        limit=1,
        occurred_from=first.occurred_from,
        occurred_to=first.occurred_to,
    )
    assert second.items == ()
    assert reader.calls[1]["before_occurred_at"] == event(0).occurred_at
    assert reader.calls[1]["before_id"] == event(0).id


async def test_audit_cursor_rejects_filter_or_organization_reuse() -> None:
    reader = Reader((event(0), event(1)))
    codec = HmacAuditCursorCodec(KEY)
    context = TenantContext(UUID(int=200), UUID(int=300), "request-list")
    use_case = ListTenantAuditEventsUseCase(lambda _: ReadUnitOfWork(reader), codec, FixedClock())
    first = await use_case.execute(context=context, has_capability=True, cursor=None, limit=1)

    with pytest.raises(InvalidAuditCursor):
        await use_case.execute(
            context=context,
            has_capability=True,
            cursor=first.next_cursor,
            limit=1,
            occurred_from=first.occurred_from,
            occurred_to=first.occurred_to,
            entity_type="organization",
        )
    with pytest.raises(InvalidAuditCursor):
        await use_case.execute(
            context=TenantContext(context.actor_id, uuid4(), "request-other"),
            has_capability=True,
            cursor=first.next_cursor,
            limit=1,
            occurred_from=first.occurred_from,
            occurred_to=first.occurred_to,
        )


async def test_audit_validates_capability_scope_period_and_entity_combination() -> None:
    reader = Reader(())
    tenant = ListTenantAuditEventsUseCase(lambda _: ReadUnitOfWork(reader), HmacAuditCursorCodec(KEY), FixedClock())
    platform = ListPlatformAuditEventsUseCase(lambda _: ReadUnitOfWork(reader), HmacAuditCursorCodec(KEY), FixedClock())
    tenant_context = TenantContext(uuid4(), uuid4(), "request-tenant")

    with pytest.raises(InsufficientCapability):
        await tenant.execute(context=tenant_context, has_capability=False, cursor=None, limit=50)
    with pytest.raises(ValueError, match="portée"):
        await tenant.execute(
            context=tenant_context,
            has_capability=True,
            cursor=None,
            limit=50,
            action="organization.provisioned",
        )
    with pytest.raises(ValueError, match="90 jours"):
        await tenant.execute(
            context=tenant_context,
            has_capability=True,
            cursor=None,
            limit=50,
            occurred_from=NOW - timedelta(days=91),
            occurred_to=NOW,
        )
    with pytest.raises(ValueError, match="entity_type"):
        await tenant.execute(
            context=tenant_context,
            has_capability=True,
            cursor=None,
            limit=50,
            entity_id=uuid4(),
        )
    result = await platform.execute(
        context=ActorContext(uuid4(), "request-platform"),
        has_capability=True,
        cursor=None,
        limit=50,
        action="organization.provisioned",
    )
    assert result.items == ()


class CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "session"
        return self.identity


class ListAudit:
    def __init__(self, item: AuditEventView) -> None:
        self.item = item
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs) -> AuditEventPage:
        self.calls.append(kwargs)
        if not kwargs["has_capability"]:
            raise InsufficientCapability
        return AuditEventPage((self.item,), None, NOW - timedelta(days=30), NOW)


def identity(*, role: MembershipRole | None = MembershipRole.ADMIN, platform: bool = False) -> AuthenticatedIdentity:
    user_id = UUID(int=200)
    organization_id = UUID(int=300)
    membership = (
        MembershipIdentity(
            UUID(int=400),
            organization_id,
            "Entreprise Exemple",
            role,
            MembershipStatus.ACTIVE,
            OrganizationStatus.ACTIVE,
            NOW,
        )
        if role is not None
        else None
    )
    user = UserIdentity(
        user_id,
        "actor@example.ca",
        "Acteur",
        "hash",
        UserStatus.ACTIVE,
        PlatformRole.PLATFORM_ADMIN if platform else None,
        organization_id if membership else None,
        1,
        (membership,) if membership else (),
    )
    return AuthenticatedIdentity(user, membership, "csrf")


def audit_app(authenticated: AuthenticatedIdentity) -> tuple[object, ListAudit, ListAudit]:
    tenant = ListAudit(event(0))
    platform = ListAudit(event(0, action="organization.provisioned"))
    app = create_app(
        container=AppContainer(
            settings=Settings(cors_allowed_origins=("http://test",)),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            get_current_session=CurrentSession(authenticated),  # type: ignore[arg-type]
            list_tenant_audit_events=tenant,  # type: ignore[arg-type]
            list_platform_audit_events=platform,  # type: ignore[arg-type]
        )
    )
    return app, tenant, platform


async def test_audit_api_serializes_minimal_event_and_rejects_client_scope() -> None:
    app, tenant, _ = audit_app(identity())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "session")
        response = await client.get("/api/audit-events")
        invalid = await client.get("/api/audit-events?organization_id=00000000-0000-0000-0000-00000000012c")

    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("no-store")
    assert response.json()["items"][0]["actor"] == {
        "kind": "user",
        "id": "00000000-0000-0000-0000-0000000000c8",
        "display_name": "Gestionnaire",
    }
    assert "email" not in str(response.json()).casefold()
    assert tenant.calls[0]["limit"] == 50
    assert invalid.status_code == 422
    assert invalid.json()["error"]["fields"] == {"organization_id": "Paramètre interdit."}


async def test_audit_api_enforces_tenant_and_platform_capabilities() -> None:
    sales_app, _, _ = audit_app(identity(role=MembershipRole.SALES))
    platform_app, _, platform = audit_app(identity(role=None, platform=True))
    async with AsyncClient(transport=ASGITransport(app=sales_app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "session")
        denied = await client.get("/api/audit-events")
    async with AsyncClient(transport=ASGITransport(app=platform_app), base_url="http://test") as client:
        client.cookies.set("prospect_session", "session")
        allowed = await client.get("/api/platform/audit-events")
        tenant_denied = await client.get("/api/audit-events")

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert platform.calls[0]["has_capability"] is True
    assert tenant_denied.status_code == 403
