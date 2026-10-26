"""Checkout offers are restricted to tenant billing administrators and test prices."""

from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.ports.catalog import CheckoutPlanOption
from backend.app.application.use_cases.catalog import GetOrganizationCatalogUseCase
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.catalog import CurrencyCode, PlanCode
from backend.app.domain.identity import (
    AuthenticatedIdentity,
    MembershipIdentity,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    UserIdentity,
    UserStatus,
)

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)


class Clock:
    def now(self) -> datetime:
        return NOW


class CurrentSession:
    def __init__(self, authenticated: AuthenticatedIdentity) -> None:
        self.authenticated = authenticated

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "test-session"
        return self.authenticated


class Reader:
    async def list_checkout_options(self, **kwargs: object) -> tuple[CheckoutPlanOption, ...]:
        assert kwargs["now"] == NOW
        return (
            CheckoutPlanOption(uuid4(), PlanCode.STARTER, 1, CurrencyCode.CAD, 2500, "monthly"),
            CheckoutPlanOption(uuid4(), PlanCode.STARTER, 2, CurrencyCode.EUR, 2300, "monthly"),
            CheckoutPlanOption(uuid4(), PlanCode.STARTER, 3, CurrencyCode.XAF, 10000, "monthly"),
        )

    async def get_current(self, **kwargs: object):
        raise AssertionError("This endpoint must not read the tenant contract")


def identity(role: MembershipRole) -> AuthenticatedIdentity:
    organization_id = uuid4()
    membership = MembershipIdentity(
        uuid4(), organization_id, "Test", role, MembershipStatus.ACTIVE, OrganizationStatus.ACTIVE, NOW
    )
    user = UserIdentity(
        uuid4(), "test@example.ca", "Test", "hash", UserStatus.ACTIVE, None, organization_id, 1, (membership,)
    )
    return AuthenticatedIdentity(user, membership, "csrf-test")


def app(role: MembershipRole, *, mode: str = "stripe_sandbox"):
    settings = Settings(
        cors_allowed_origins=("http://test",),
        billing_provider_mode=mode,
        billing_stripe_test_secret_key="sk_test_example",
        billing_stripe_webhook_secret="whsec_example",
        billing_stripe_price_cad_monthly="price_test_cad",
        billing_stripe_price_xaf_monthly="price_test_xaf",
    )
    return create_app(
        container=AppContainer(
            settings=settings,
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            get_current_session=CurrentSession(identity(role)),  # type: ignore[arg-type]
            get_organization_catalog=GetOrganizationCatalogUseCase(Reader(), Clock()),  # type: ignore[arg-type]
        )
    )


async def test_checkout_options_include_only_configured_test_currencies() -> None:
    async with AsyncClient(transport=ASGITransport(app=app(MembershipRole.ADMIN)), base_url="http://test") as client:
        client.cookies.set("prospect_session", "test-session")
        response = await client.get("/api/billing/checkout-options")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    options = response.json()["options"]
    assert [item["currency"] for item in options] == ["CAD", "XAF"]
    assert options[1]["amount_minor"] == 10000
    assert all(
        set(item) == {"id", "code", "version_number", "currency", "amount_minor", "billing_cycle"} for item in options
    )
    assert "price_test_xaf" not in response.text


async def test_checkout_options_require_billing_capability() -> None:
    async with AsyncClient(transport=ASGITransport(app=app(MembershipRole.MANAGER)), base_url="http://test") as client:
        client.cookies.set("prospect_session", "test-session")
        response = await client.get("/api/billing/checkout-options")

    assert response.status_code == 403


async def test_checkout_options_are_disabled_outside_sandbox() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app(MembershipRole.ADMIN, mode="disabled")), base_url="http://test"
    ) as client:
        client.cookies.set("prospect_session", "test-session")
        response = await client.get("/api/billing/checkout-options")

    assert response.status_code == 503
