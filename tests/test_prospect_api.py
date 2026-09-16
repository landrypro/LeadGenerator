from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.models import GoogleAccessOwner
from backend.app.application.use_cases.prospects import (
    GoogleProspectAddItem,
    GoogleProspectAddOutcome,
    GoogleProspectInput,
    ProspectPage,
)
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
from backend.app.domain.prospect import ProspectOrigin, ProspectStageCode, ProspectView

CSRF_TOKEN = "csrf-prospect-api"
SESSION_TOKEN = "prospect-api-session"


def prospect_view(
    *, google_place_id: str | None = "place-1", internal_alias: str = "Prospect Google ABC123"
) -> ProspectView:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    return ProspectView(
        id=uuid4(),
        organization_id=uuid4(),
        internal_alias=internal_alias,
        origin=ProspectOrigin.GOOGLE_PLACE if google_place_id else ProspectOrigin.MANUAL,
        source_label="google_places:text_search" if google_place_id else "manual:user_entry",
        google_place_id=google_place_id,
        stage_code=ProspectStageCode.NEW,
        priority=0,
        version=1,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )


def identity() -> AuthenticatedIdentity:
    membership = MembershipIdentity(
        id=uuid4(),
        organization_id=uuid4(),
        organization_name="Entreprise QA",
        role=MembershipRole.SALES,
        status=MembershipStatus.ACTIVE,
        organization_status=OrganizationStatus.ACTIVE,
        created_at=datetime.now(UTC),
    )
    user = UserIdentity(
        id=uuid4(),
        email="sales@example.ca",
        display_name="Vente",
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


class AddGoogleProspectsStub:
    def __init__(self) -> None:
        self.calls = []

    async def execute(
        self,
        *,
        context: object,
        owner: GoogleAccessOwner,
        selection_token: str,
        items: tuple[GoogleProspectInput, ...],
        has_capability: bool,
    ) -> GoogleProspectAddOutcome:
        self.calls.append(
            {
                "context": context,
                "owner": owner,
                "selection_token": selection_token,
                "items": items,
                "has_capability": has_capability,
            }
        )
        return GoogleProspectAddOutcome(
            items=(
                GoogleProspectAddItem(
                    place_id=items[0].place_id,
                    disposition="created",
                    prospect=prospect_view(
                        google_place_id=items[0].place_id,
                        internal_alias=items[0].internal_alias,
                    ),
                ),
            )
        )


class ListProspectsStub:
    async def execute(
        self, *, context: object, has_capability: bool, cursor: str | None, limit: int, **filters: object
    ) -> ProspectPage:
        del context, has_capability, cursor, limit, filters
        return ProspectPage(items=(prospect_view(),), next_cursor=None)


class UpdateProspectProfileStub:
    def __init__(self) -> None:
        self.calls = []

    async def execute(self, **kwargs: object) -> ProspectView:
        self.calls.append(kwargs)
        return prospect_view(google_place_id=None)


def app_with_prospects() -> tuple[object, AddGoogleProspectsStub, UpdateProspectProfileStub, AuthenticatedIdentity]:
    settings = Settings(cors_allowed_origins=("http://test",))
    authenticated = identity()
    add_google = AddGoogleProspectsStub()
    update_profile = UpdateProspectProfileStub()
    container = AppContainer(
        settings=settings,
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=CurrentSession(authenticated),  # type: ignore[arg-type]
        add_google_prospects=add_google,  # type: ignore[arg-type]
        list_prospects=ListProspectsStub(),  # type: ignore[arg-type]
        update_prospect_profile=update_profile,  # type: ignore[arg-type]
    )
    return create_app(container=container), add_google, update_profile, authenticated


async def test_from_google_uses_selection_token_and_returns_no_store() -> None:
    app, add_google, _update_profile, authenticated = app_with_prospects()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.post(
            "/api/prospects/from-google",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
            json={
                "selection_token": "selection-token-long-enough-for-contract",
                "items": [{"place_id": "place-1", "internal_alias": "Plomberie Nord"}],
            },
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["items"][0]["disposition"] == "created"
    assert add_google.calls[0]["selection_token"] == "selection-token-long-enough-for-contract"
    assert add_google.calls[0]["items"] == (GoogleProspectInput(place_id="place-1", internal_alias="Plomberie Nord"),)
    assert add_google.calls[0]["owner"].user_id == authenticated.user.id
    assert add_google.calls[0]["owner"].organization_id == authenticated.active_membership.organization_id


async def test_from_google_rejects_missing_internal_alias_before_use_case() -> None:
    app, add_google, _update_profile, _authenticated = app_with_prospects()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.post(
            "/api/prospects/from-google",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
            json={
                "selection_token": "selection-token-long-enough-for-contract",
                "items": [{"place_id": "place-1", "internal_alias": ""}],
            },
        )

    assert response.status_code == 422
    assert add_google.calls == []


async def test_prospect_list_returns_no_store() -> None:
    app, _add_google, _update_profile, _authenticated = app_with_prospects()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.get("/api/prospects")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["items"][0]["google_place_id"] == "place-1"


async def test_prospect_profile_update_requires_version_and_manual_provenance() -> None:
    app, _add_google, update_profile, _authenticated = app_with_prospects()
    prospect_id = uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.patch(
            f"/api/prospects/{prospect_id}",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
            json={
                "version": 3,
                "industry_label": "Services professionnels",
                "tags": ["Prioritaire"],
                "purpose": "commercial_follow_up",
                "territory": "CA-QC",
            },
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert update_profile.calls[0]["expected_version"] == 3
    assert update_profile.calls[0]["purpose"] == "commercial_follow_up"
