from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.application.errors import CatalogConcurrentUpdate, InsufficientCapability
from backend.app.application.ports.catalog import (
    CatalogPlanView,
    OrganizationCatalogView,
    OrganizationEntitlementDecisionView,
    OrganizationPlanContractView,
)
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.catalog import CreateCatalogPlanCommand
from backend.app.bootstrap import create_app
from backend.app.config import Settings
from backend.app.container import AppContainer
from backend.app.domain.catalog import ContractState, CurrencyCode, EntitlementKey, EntitlementKind, PlanCode
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

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)


def tenant_identity(role: MembershipRole = MembershipRole.ADMIN) -> AuthenticatedIdentity:
    organization_id = uuid4()
    membership = MembershipIdentity(
        uuid4(), organization_id, "Entreprise Exemple", role, MembershipStatus.ACTIVE, OrganizationStatus.ACTIVE, NOW
    )
    user = UserIdentity(
        uuid4(), "tenant@example.ca", "Tenant", "hash", UserStatus.ACTIVE, None, organization_id, 1, (membership,)
    )
    return AuthenticatedIdentity(user, membership, "csrf-current")


def platform_identity() -> AuthenticatedIdentity:
    user = UserIdentity(
        uuid4(), "platform@example.ca", "Platform", "hash", UserStatus.ACTIVE, PlatformRole.PLATFORM_ADMIN, None, 1, ()
    )
    return AuthenticatedIdentity(user, None, "csrf-current")


class CurrentSession:
    def __init__(self, authenticated: AuthenticatedIdentity) -> None:
        self.authenticated = authenticated

    async def execute(self, token: str) -> AuthenticatedIdentity:
        assert token == "current-session"
        return self.authenticated


class CatalogReader:
    async def execute(self, **kwargs: object) -> OrganizationCatalogView:
        assert kwargs["has_capability"] is True
        context = kwargs["context"]
        assert isinstance(context, TenantContext)
        contract = OrganizationPlanContractView(
            uuid4(), context.organization_id, uuid4(), ContractState.ACTIVE, CurrencyCode.CAD, NOW, None, 3
        )
        entitlement = OrganizationEntitlementDecisionView(
            EntitlementKey.ACTIVE_MEMBERS_MAX,
            "allowed",
            EntitlementKind.LIMIT,
            5,
            None,
            "override",
            None,
            (("contract", True), ("plan_version", True), ("override", True)),
        )
        return OrganizationCatalogView(contract, (entitlement,))


class CatalogAdministration:
    def __init__(self, *, conflict: bool = False) -> None:
        self.conflict = conflict
        self.operations: list[UUID] = []

    async def create_plan(self, **kwargs: object) -> CatalogPlanView:
        if not kwargs["has_platform_capability"]:
            raise InsufficientCapability
        command = kwargs["command"]
        assert isinstance(command, CreateCatalogPlanCommand)
        self.operations.append(command.operation_id)
        return CatalogPlanView(uuid4(), PlanCode.CUSTOM, "draft", 3, 1)

    async def change_contract_state(self, **kwargs: object) -> OrganizationPlanContractView:
        if not kwargs["has_platform_capability"]:
            raise InsufficientCapability
        if self.conflict:
            raise CatalogConcurrentUpdate(7)
        return OrganizationPlanContractView(
            uuid4(), uuid4(), uuid4(), ContractState.SUSPENDED, CurrencyCode.CAD, NOW, None, 2
        )


def api_app(authenticated: AuthenticatedIdentity, administration: CatalogAdministration | None = None) -> FastAPI:
    return create_app(
        container=AppContainer(
            settings=Settings(cors_allowed_origins=("http://test",)),
            search_google_places=object(),  # type: ignore[arg-type]
            get_map_snapshot=object(),  # type: ignore[arg-type]
            get_current_session=CurrentSession(authenticated),  # type: ignore[arg-type]
            get_organization_catalog=CatalogReader(),  # type: ignore[arg-type]
            catalog_administration=administration or CatalogAdministration(),  # type: ignore[arg-type]
        )
    )


async def client_for(
    authenticated: AuthenticatedIdentity, administration: CatalogAdministration | None = None
) -> AsyncClient:
    client = AsyncClient(transport=ASGITransport(app=api_app(authenticated, administration)), base_url="http://test")
    client.cookies.set("prospect_session", "current-session")
    return client


async def test_tenant_catalog_view_is_minimized_and_no_store() -> None:
    async with await client_for(tenant_identity()) as client:
        response = await client.get("/api/organization/catalog")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    payload = response.json()
    assert set(payload["contract"]) == {"id", "state", "currency", "effective_from", "effective_until", "version"}
    assert set(payload["entitlements"][0]) == {
        "key",
        "code",
        "value_kind",
        "integer_value",
        "boolean_value",
        "source",
        "reason",
        "provenance",
    }
    assert "plan_version_id" not in payload["contract"]
    assert payload["entitlements"][0]["provenance"] == [
        {"source": "contract", "applied": True},
        {"source": "plan_version", "applied": True},
        {"source": "override", "applied": True},
    ]


async def test_platform_catalog_mutations_require_platform_capability_and_csrf() -> None:
    operation_id = uuid4()
    payload = {"code": "custom", "display_order": 3, "operation_id": str(operation_id)}
    administration = CatalogAdministration()
    async with await client_for(platform_identity(), administration) as platform_client:
        accepted = await platform_client.post(
            "/api/platform/catalog/plans",
            json=payload,
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-current"},
        )
        missing_csrf = await platform_client.post("/api/platform/catalog/plans", json=payload)
    async with await client_for(tenant_identity()) as tenant_client:
        denied = await tenant_client.post(
            "/api/platform/catalog/plans",
            json=payload,
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-current"},
        )

    assert accepted.status_code == 200
    assert accepted.headers["cache-control"] == "no-store, max-age=0"
    assert administration.operations == [operation_id]
    assert (missing_csrf.status_code, missing_csrf.json()["error"]["code"]) == (403, "request_rejected")
    assert (denied.status_code, denied.json()["error"]["code"]) == (403, "insufficient_capability")


async def test_catalog_conflicts_and_invalid_commands_have_stable_statuses() -> None:
    conflict_id = uuid4()
    conflicting = CatalogAdministration(conflict=True)
    async with await client_for(platform_identity(), conflicting) as client:
        conflict = await client.post(
            f"/api/platform/catalog/contracts/{conflict_id}/state",
            json={"version": 1, "state": "suspended", "operation_id": str(uuid4())},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-current"},
        )
        invalid = await client.post(
            "/api/platform/catalog/plans",
            json={"code": "not-a-plan", "display_order": -1, "operation_id": str(uuid4())},
            headers={"Origin": "http://test", "X-CSRF-Token": "csrf-current"},
        )

    assert (conflict.status_code, conflict.json()["error"]["code"]) == (409, "catalog_version_conflict")
    assert conflict.json()["error"]["fields"] == {"version": "7"}
    assert invalid.status_code == 422
