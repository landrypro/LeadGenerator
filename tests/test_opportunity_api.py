from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.use_cases.opportunities import OpportunityPage
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
from backend.app.domain.opportunity import (
    OpportunityCurrencyAggregate,
    OpportunityDraft,
    OpportunityProspectSummary,
    OpportunityStageCode,
    OpportunityView,
)

CSRF_TOKEN = "csrf-opportunity-api"
SESSION_TOKEN = "opportunity-api-session"


def _identity() -> AuthenticatedIdentity:
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=uuid4(),
        organization_name="Entreprise QA",
        role=MembershipRole.SALES,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=datetime(2026, 9, 10, tzinfo=UTC),
    )
    return AuthenticatedIdentity(
        user=UserIdentity(
            id=uuid4(),
            email="sales@example.ca",
            display_name="Vente",
            password_hash="not-serialized",
            status=UserStatus.ACTIVE,
            platform_role=None,
            last_active_organization_id=membership.organization_id,
            version=1,
            memberships=(membership,),
        ),
        active_membership=membership,
        csrf_token=CSRF_TOKEN,
    )


def _opportunity(identity: AuthenticatedIdentity) -> OpportunityView:
    now = datetime(2026, 9, 10, 12, tzinfo=UTC)
    membership = identity.active_membership
    assert membership is not None
    return OpportunityView(
        id=uuid4(),
        organization_id=membership.organization_id,
        prospect_id=uuid4(),
        owner_membership_id=membership.id,
        name="Renouvellement 2027",
        amount=Decimal("12500.5000"),
        currency_code="CAD",
        probability=40,
        stage_code=OpportunityStageCode.DISCOVERY,
        expected_close_on=date(2026, 10, 15),
        loss_reason_code=None,
        loss_reason_note=None,
        closed_at=None,
        created_by=identity.user.id,
        version=1,
        created_at=now,
        updated_at=now,
    )


class _CurrentSession:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self._identity = identity

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == SESSION_TOKEN
        return self._identity


class _CreateOpportunity:
    def __init__(self, response: OpportunityView) -> None:
        self.response = response
        self.drafts: list[OpportunityDraft] = []

    async def execute(self, *, draft: OpportunityDraft, **_kwargs: object) -> OpportunityView:
        self.drafts.append(draft)
        return self.response


class _ListOpportunities:
    def __init__(self, response: OpportunityView) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs: object) -> OpportunityPage:
        self.calls.append(kwargs)
        return OpportunityPage(items=(self.response,), next_cursor=None, has_more=False)


class _ListSummaries:
    def __init__(self, opportunity: OpportunityView) -> None:
        self.calls: list[dict[str, object]] = []
        self.summary = OpportunityProspectSummary(
            prospect_id=opportunity.prospect_id,
            open_count=1,
            has_won_opportunity=False,
            next_expected_close_on=opportunity.expected_close_on,
            overdue_open_count=0,
            aggregates_by_currency=(
                OpportunityCurrencyAggregate(
                    currency_code="CAD",
                    count=1,
                    amount_total=Decimal("12500.5000"),
                    weighted_amount_total=Decimal("5000.2000"),
                    open_count=1,
                    won_count=0,
                    lost_count=0,
                    overdue_open_count=0,
                ),
            ),
        )

    async def execute(self, **kwargs: object) -> tuple[OpportunityProspectSummary, ...]:
        self.calls.append(kwargs)
        return (self.summary,)


def _app() -> tuple[object, _CreateOpportunity, _ListOpportunities, _ListSummaries, OpportunityView]:
    identity = _identity()
    opportunity = _opportunity(identity)
    create = _CreateOpportunity(opportunity)
    listing = _ListOpportunities(opportunity)
    summaries = _ListSummaries(opportunity)
    container = AppContainer(
        settings=Settings(cors_allowed_origins=("http://test",)),
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=_CurrentSession(identity),  # type: ignore[arg-type]
        create_opportunity=create,  # type: ignore[arg-type]
        list_opportunities=listing,  # type: ignore[arg-type]
        list_opportunity_summaries=summaries,  # type: ignore[arg-type]
    )
    return create_app(container=container), create, listing, summaries, opportunity


async def test_create_opportunity_uses_member_as_default_owner_and_disables_cache() -> None:
    app, create, _listing, _summaries, opportunity = _app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.post(
            f"/api/prospects/{opportunity.prospect_id}/opportunities",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
            json={
                "name": "Renouvellement 2027",
                "amount": "12500.50",
                "currency_code": "CAD",
                "probability": 40,
                "expected_close_on": "2026-10-15",
                "idempotency_key": str(uuid4()),
            },
        )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["weighted_amount"] == "5000.2000"
    assert create.drafts[0].amount == Decimal("12500.50")


async def test_create_opportunity_exposes_a_safe_field_error_for_exponent_notation() -> None:
    app, create, _listing, _summaries, opportunity = _app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.post(
            f"/api/prospects/{opportunity.prospect_id}/opportunities",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
            json={
                "name": "Renouvellement 2027",
                "amount": "1e3",
                "currency_code": "CAD",
                "probability": 40,
                "expected_close_on": "2026-10-15",
                "idempotency_key": str(uuid4()),
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "opportunity_command_invalid"
    assert response.json()["error"]["message"] == "La commande opportunité est invalide."
    assert response.json()["error"]["fields"] == {"amount": "Le montant doit être écrit sans notation exponentielle."}
    assert create.drafts == []


async def test_create_opportunity_exposes_a_safe_field_error_for_probability() -> None:
    app, _create, _listing, _summaries, opportunity = _app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.post(
            f"/api/prospects/{opportunity.prospect_id}/opportunities",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
            json={
                "name": "Renouvellement 2027",
                "amount": "100",
                "currency_code": "CAD",
                "probability": 101,
                "expected_close_on": "2026-10-15",
                "idempotency_key": str(uuid4()),
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert response.json()["error"]["message"] == "La commande opportunité est invalide."
    assert response.json()["error"]["fields"] == {"probability": "Saisissez une probabilité entière entre 0 et 100."}


async def test_portfolio_accepts_filters_and_rejects_invalid_csrf() -> None:
    app, _create, listing, _summaries, _opportunity_view = _app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        portfolio = await client.get("/api/opportunities?stage=discovery&currency_code=CAD&q=Renouvellement")
        rejected = await client.post(
            f"/api/prospects/{uuid4()}/opportunities",
            headers={"Origin": "http://test", "X-CSRF-Token": "invalid"},
            json={
                "name": "Nouvelle opportunité",
                "amount": "100",
                "currency_code": "CAD",
                "probability": 10,
                "expected_close_on": "2026-10-15",
                "idempotency_key": str(uuid4()),
            },
        )

    assert portfolio.status_code == 200
    assert portfolio.headers["cache-control"] == "no-store, max-age=0"
    assert listing.calls[0]["stage_codes"] == (OpportunityStageCode.DISCOVERY,)
    assert listing.calls[0]["currency_code"] == "CAD"
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "csrf_failed"


async def test_prospect_opportunity_summaries_are_batch_read_only_and_not_cached() -> None:
    app, _create, _listing, summaries, opportunity = _app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.get(f"/api/prospects/opportunity-summaries?prospect_id={opportunity.prospect_id}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["items"][0]["prospect_id"] == str(opportunity.prospect_id)
    assert summaries.calls[0]["prospect_ids"] == (opportunity.prospect_id,)
