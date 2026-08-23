from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app.application.models import GoogleAccessOwner
from backend.app.application.use_cases.prospects import GoogleProspectAddItem, GoogleProspectAddOutcome, ProspectPage
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


def prospect_view(*, google_place_id: str | None = "place-1") -> ProspectView:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    return ProspectView(
        id=uuid4(),
        organization_id=uuid4(),
        internal_alias="Prospect Google ABC123",
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
        place_ids: tuple[str, ...],
        has_capability: bool,
    ) -> GoogleProspectAddOutcome:
        self.calls.append(
            {
                "context": context,
                "owner": owner,
                "selection_token": selection_token,
                "place_ids": place_ids,
                "has_capability": has_capability,
            }
        )
        return GoogleProspectAddOutcome(
            items=(
                GoogleProspectAddItem(
                    place_id=place_ids[0],
                    disposition="created",
                    prospect=prospect_view(google_place_id=place_ids[0]),
                ),
            )
        )


class ListProspectsStub:
    async def execute(self, *, context: object, has_capability: bool, cursor: str | None, limit: int) -> ProspectPage:
        del context, has_capability, cursor, limit
        return ProspectPage(items=(prospect_view(),), next_cursor=None)


def app_with_prospects() -> tuple[object, AddGoogleProspectsStub, AuthenticatedIdentity]:
    settings = Settings(cors_allowed_origins=("http://test",))
    authenticated = identity()
    add_google = AddGoogleProspectsStub()
    container = AppContainer(
        settings=settings,
        search_google_places=object(),  # type: ignore[arg-type]
        get_map_snapshot=object(),  # type: ignore[arg-type]
        get_current_session=CurrentSession(authenticated),  # type: ignore[arg-type]
        add_google_prospects=add_google,  # type: ignore[arg-type]
        list_prospects=ListProspectsStub(),  # type: ignore[arg-type]
    )
    return create_app(container=container), add_google, authenticated


async def test_from_google_uses_selection_token_and_returns_no_store() -> None:
    app, add_google, authenticated = app_with_prospects()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.post(
            "/api/prospects/from-google",
            headers={"Origin": "http://test", "X-CSRF-Token": CSRF_TOKEN},
            json={"selection_token": "selection-token-long-enough-for-contract", "place_ids": ["place-1"]},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["items"][0]["disposition"] == "created"
    assert add_google.calls[0]["selection_token"] == "selection-token-long-enough-for-contract"
    assert add_google.calls[0]["place_ids"] == ("place-1",)
    assert add_google.calls[0]["owner"].user_id == authenticated.user.id
    assert add_google.calls[0]["owner"].organization_id == authenticated.active_membership.organization_id


async def test_prospect_list_returns_no_store() -> None:
    app, _add_google, _authenticated = app_with_prospects()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("prospect_session", SESSION_TOKEN)
        response = await client.get("/api/prospects")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.json()["items"][0]["google_place_id"] == "place-1"
