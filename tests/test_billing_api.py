from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import BillingOperationError
from backend.app.application.use_cases.billing import BillingSessionGrant
from backend.app.application.use_cases.billing_refunds import BillingRefundOutcome
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.billing import BillingErrorCode
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

NOW = datetime(2026, 10, 10, 15, tzinfo=UTC)


def _identity(
    role: MembershipRole = MembershipRole.ADMIN, *, age: timedelta = timedelta(), platform: bool = False
) -> AuthenticatedIdentity:
    organization_id = uuid4()
    membership = MembershipIdentity(
        uuid4(), organization_id, "Entreprise", role, MembershipStatus.ACTIVE, OrganizationStatus.ACTIVE, NOW
    )
    user = UserIdentity(
        uuid4(),
        "admin@example.ca",
        "Admin",
        "hash",
        UserStatus.ACTIVE,
        PlatformRole.PLATFORM_ADMIN if platform else None,
        organization_id,
        1,
        (membership,),
    )
    return AuthenticatedIdentity(user, membership, "csrf-current", NOW - age)


class _CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "session-current"
        return self.identity


class _BillingSessions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create_checkout(self, **kwargs: object) -> BillingSessionGrant:
        self.calls.append(kwargs)
        if kwargs["authorized"] is not True:
            raise BillingOperationError(BillingErrorCode.CAPABILITY_REQUIRED)
        return BillingSessionGrant("http://billing-simulator.local/checkout/opaque", NOW + timedelta(minutes=30))

    async def create_portal(self, **kwargs: object) -> BillingSessionGrant:
        self.calls.append(kwargs)
        if kwargs["authorized"] is not True:
            raise BillingOperationError(BillingErrorCode.CAPABILITY_REQUIRED)
        return BillingSessionGrant("http://billing-simulator.local/portal/opaque", NOW + timedelta(minutes=30))


class _BillingRefunds:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def request_refund(self, **kwargs: object) -> BillingRefundOutcome:
        self.calls.append(kwargs)
        if kwargs["authorized"] is not True:
            raise BillingOperationError(BillingErrorCode.CAPABILITY_REQUIRED)
        return BillingRefundOutcome(uuid4(), "approved")


def _app(identity: AuthenticatedIdentity, billing: _BillingSessions, refunds: _BillingRefunds | None = None) -> FastAPI:
    return create_app(
        container=AppContainer(
            settings=Settings(cors_allowed_origins=("http://test",)),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            get_current_session=_CurrentSession(identity),  # type: ignore[arg-type]
            billing_sessions=billing,  # type: ignore[arg-type]
            billing_refunds=refunds,
        )
    )


async def _client(
    identity: AuthenticatedIdentity, billing: _BillingSessions, refunds: _BillingRefunds | None = None
) -> AsyncClient:
    client = AsyncClient(transport=ASGITransport(app=_app(identity, billing, refunds)), base_url="http://test")
    client.cookies.set("prospect_session", "session-current")
    return client


async def test_checkout_response_is_minimized_no_store_and_uses_closed_return_target() -> None:
    billing = _BillingSessions()
    async with await _client(_identity(), billing) as client:
        response = await client.post(
            "/api/billing/checkout-session",
            json={"plan_version_id": str(uuid4()), "return_target": "subscription"},
            headers={"origin": "http://test", "x-csrf-token": "csrf-current", "idempotency-key": "key-1"},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert set(response.json()) == {"url", "expires_at"}
    assert billing.calls[0]["idempotency_key"] == "key-1"


async def test_client_cannot_supply_amount_currency_provider_reference_or_return_url() -> None:
    billing = _BillingSessions()
    async with await _client(_identity(), billing) as client:
        response = await client.post(
            "/api/billing/checkout-session",
            json={
                "plan_version_id": str(uuid4()),
                "return_target": "https://evil.example",
                "currency": "USD",
                "amount": 1,
                "provider_price_reference": "forged",
            },
            headers={"origin": "http://test", "x-csrf-token": "csrf-current", "idempotency-key": "key-2"},
        )

    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["error"]["code"] == "validation_failed"
    assert billing.calls == []


async def test_billing_mutation_requires_idempotency_csrf_and_admin_capability() -> None:
    billing = _BillingSessions()
    body = {"return_target": "subscription"}
    async with await _client(_identity(), billing) as client:
        missing_key = await client.post(
            "/api/billing/portal-session",
            json=body,
            headers={"origin": "http://test", "x-csrf-token": "csrf-current"},
        )
        bad_csrf = await client.post(
            "/api/billing/portal-session",
            json=body,
            headers={"origin": "http://test", "x-csrf-token": "wrong", "idempotency-key": "key-3"},
        )
    async with await _client(_identity(MembershipRole.MANAGER), billing) as client:
        forbidden = await client.post(
            "/api/billing/portal-session",
            json=body,
            headers={"origin": "http://test", "x-csrf-token": "csrf-current", "idempotency-key": "key-4"},
        )

    assert missing_key.status_code == 422
    assert bad_csrf.status_code == 403
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "billing_capability_required"
    assert all(
        response.headers["cache-control"] == "no-store, max-age=0" for response in (missing_key, bad_csrf, forbidden)
    )


async def test_platform_refund_is_minimized_and_never_accepts_provider_references() -> None:
    billing = _BillingSessions()
    refunds = _BillingRefunds()
    async with await _client(_identity(platform=True), billing, refunds) as client:
        response = await client.post(
            "/api/platform/billing/refunds",
            json={
                "organization_id": str(uuid4()),
                "subscription_id": str(uuid4()),
                "approved": True,
                "justification_code": "policy_within_14_days",
            },
            headers={"origin": "http://test", "x-csrf-token": "csrf-current", "idempotency-key": "refund-1"},
        )
        forged = await client.post(
            "/api/platform/billing/refunds",
            json={
                "organization_id": str(uuid4()),
                "subscription_id": str(uuid4()),
                "approved": True,
                "justification_code": "policy_within_14_days",
                "provider_payment_reference": "forged",
            },
            headers={"origin": "http://test", "x-csrf-token": "csrf-current", "idempotency-key": "refund-2"},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert set(response.json()) == {"refund_id", "state"}
    assert refunds.calls[0]["authorized"] is True
    assert forged.status_code == 422
    assert refunds.calls == refunds.calls[:1]
