from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import InsufficientCapability
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
from backend.app.domain.prospect import (
    RetentionHoldReasonCode,
    RetentionHoldView,
    RetentionPolicyStatus,
    RetentionPolicyView,
    RetentionResourceType,
)

CSRF_TOKEN = "csrf-retention-api"
SESSION_TOKEN = "retention-api-session"
NOW = datetime(2026, 8, 14, 18, tzinfo=UTC)


def identity(role: MembershipRole = MembershipRole.ADMIN) -> AuthenticatedIdentity:
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=uuid4(),
        organization_name="Entreprise QA",
        role=role,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=NOW,
    )
    user = UserIdentity(
        id=uuid4(),
        email="admin@example.ca",
        display_name="Admin QA",
        password_hash="not-serialized",
        status=UserStatus.ACTIVE,
        platform_role=None,
        last_active_organization_id=membership.organization_id,
        version=1,
        memberships=(membership,),
    )
    return AuthenticatedIdentity(user=user, active_membership=membership, csrf_token=CSRF_TOKEN)


class CurrentSession:
    def __init__(self, authenticated_identity: AuthenticatedIdentity) -> None:
        self.identity = authenticated_identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == SESSION_TOKEN
        return self.identity


class CreateRetentionPolicyStub:
    def __init__(self, organization_id) -> None:
        self.organization_id = organization_id
        self.calls: list[dict[str, object]] = []

    async def execute(
        self,
        *,
        context: object,
        has_capability: bool,
        resource_type: RetentionResourceType,
        policy_code: str,
        label: str,
        review_after_days: int,
        archive_after_days: int | None,
        effective_from: datetime | None,
    ) -> RetentionPolicyView:
        self.calls.append(
            {
                "context": context,
                "has_capability": has_capability,
                "resource_type": resource_type,
                "policy_code": policy_code,
                "label": label,
                "review_after_days": review_after_days,
                "archive_after_days": archive_after_days,
                "effective_from": effective_from,
            }
        )
        if not has_capability:
            raise InsufficientCapability
        return RetentionPolicyView(
            id=uuid4(),
            organization_id=self.organization_id,
            resource_type=resource_type,
            policy_code=policy_code,
            label=label,
            status=RetentionPolicyStatus.DRAFT,
            review_after_days=review_after_days,
            archive_after_days=archive_after_days,
            effective_from=effective_from or NOW,
            effective_until=None,
            approved_at=None,
            approved_by=None,
            created_by=None,
            created_at=NOW,
            updated_at=NOW,
            version=1,
        )


class GetRetentionPolicyStub:
    def __init__(self, organization_id) -> None:
        self.organization_id = organization_id

    async def execute(
        self,
        *,
        context: object,
        has_capability: bool,
        policy_id,
    ) -> RetentionPolicyView:
        if not has_capability:
            raise InsufficientCapability
        return RetentionPolicyView(
            id=policy_id,
            organization_id=self.organization_id,
            resource_type=RetentionResourceType.PROSPECT,
            policy_code="commercial_review",
            label="Revue commerciale",
            status=RetentionPolicyStatus.ACTIVE,
            review_after_days=365,
            archive_after_days=None,
            effective_from=NOW,
            effective_until=None,
            approved_at=NOW,
            approved_by=None,
            created_by=None,
            created_at=NOW,
            updated_at=NOW,
            version=2,
        )


class GetRetentionHoldStub:
    def __init__(self) -> None:
        self.resource_id = uuid4()

    async def execute(
        self,
        *,
        context: object,
        has_capability: bool,
        hold_id,
    ) -> RetentionHoldView:
        if not has_capability:
            raise InsufficientCapability
        return RetentionHoldView(
            id=hold_id,
            organization_id=uuid4(),
            resource_type=RetentionResourceType.PROSPECT,
            resource_id=self.resource_id,
            reason_code=RetentionHoldReasonCode.QUALITY_REVIEW,
            note="Note interne sensible",
            placed_at=NOW,
            placed_by=None,
            released_at=None,
            released_by=None,
            release_reason_code=None,
            command_fingerprint="hold-fingerprint",
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )


class ListRetentionHoldsStub:
    def __init__(self, hold: RetentionHoldView) -> None:
        self.hold = hold

    async def execute(
        self,
        *,
        context: object,
        has_capability: bool,
        resource_type: RetentionResourceType | None,
        resource_id,
        active_only: bool | None,
        limit: int,
    ) -> tuple[RetentionHoldView, ...]:
        if not has_capability:
            raise InsufficientCapability
        return (self.hold,)


def app_with_retention_route(role: MembershipRole = MembershipRole.ADMIN):
    authenticated = identity(role)
    membership = authenticated.active_membership
    assert membership is not None
    stub = CreateRetentionPolicyStub(membership.organization_id)
    get_policy = GetRetentionPolicyStub(membership.organization_id)
    get_hold = GetRetentionHoldStub()
    list_holds = ListRetentionHoldsStub(
        RetentionHoldView(
            id=uuid4(),
            organization_id=membership.organization_id,
            resource_type=RetentionResourceType.PROSPECT,
            resource_id=get_hold.resource_id,
            reason_code=RetentionHoldReasonCode.QUALITY_REVIEW,
            note="Note interne sensible",
            placed_at=NOW,
            placed_by=None,
            released_at=None,
            released_by=None,
            release_reason_code=None,
            command_fingerprint="hold-list-fingerprint",
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    container = AppContainer(
        settings=Settings(cors_allowed_origins=("http://test",)),
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=CurrentSession(authenticated),  # type: ignore[arg-type]
        create_retention_policy=stub,  # type: ignore[arg-type]
        get_retention_policy=get_policy,  # type: ignore[arg-type]
        get_retention_hold=get_hold,  # type: ignore[arg-type]
        list_retention_holds=list_holds,  # type: ignore[arg-type]
    )
    return create_app(container=container), stub


async def test_create_retention_policy_uses_capability_csrf_and_no_store() -> None:
    app, stub = app_with_retention_route()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.post(
            "/api/retention/policies",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
            json={
                "resource_type": "prospect",
                "policy_code": "commercial_review",
                "label": "Revue commerciale",
                "review_after_days": 365,
            },
        )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["status"] == "draft"
    assert stub.calls[0]["has_capability"] is True
    assert stub.calls[0]["resource_type"] is RetentionResourceType.PROSPECT


async def test_sales_cannot_manage_retention_policy() -> None:
    app, _stub = app_with_retention_route(MembershipRole.SALES)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.post(
            "/api/retention/policies",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
            json={
                "resource_type": "prospect",
                "policy_code": "commercial_review",
                "label": "Revue commerciale",
                "review_after_days": 365,
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_capability"


async def test_retention_policy_detail_is_readable_and_no_store() -> None:
    app, _stub = app_with_retention_route()
    policy_id = uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.get(f"/api/retention/policies/{policy_id}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["id"] == str(policy_id)
    assert response.json()["status"] == "active"


async def test_retention_hold_detail_keeps_note_but_list_hides_it() -> None:
    app, _stub = app_with_retention_route()
    hold_id = uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        detail = await client.get(f"/api/retention/holds/{hold_id}")
        listing = await client.get("/api/retention/holds")

    assert detail.status_code == 200
    assert detail.json()["note"] == "Note interne sensible"
    assert listing.status_code == 200
    assert listing.json()["items"][0]["note"] is None


async def test_import_declaration_rejects_multipart_before_upload_logic() -> None:
    app, _stub = app_with_retention_route()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.post(
            "/api/import-declarations",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN, "Idempotency-Key": "import-file"},
            files={"file": ("prospects.csv", b"name,email\nA,a@example.ca\n", "text/csv")},
        )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "json_required"
