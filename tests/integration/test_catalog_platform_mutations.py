"""Preuves réelles des commandes internes P52-03."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from backend.app.application.errors import CatalogApprovalRequired
from backend.app.application.tenancy import ActorContext
from backend.app.application.use_cases.catalog import (
    AttachOrganizationPlanContractCommand,
    CatalogAdministrationUseCases,
    CreateCatalogPlanCommand,
    CreateCatalogPlanVersionCommand,
    ProposePlanContractOverrideCommand,
)
from backend.app.domain.catalog import (
    ENTITLEMENT_REGISTRY,
    ContractState,
    CurrencyCode,
    EntitlementKey,
    EntitlementKind,
    EntitlementValue,
    OverrideState,
    PlanCode,
)
from backend.app.infrastructure.clock import SystemClock
from backend.app.infrastructure.postgres import PostgresDatabase

pytestmark = pytest.mark.integration


def _urls() -> tuple[str, str]:
    app_url, owner_url = os.environ.get("TEST_DATABASE_URL", ""), os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not app_url or not owner_url:
        pytest.skip("Les URL PostgreSQL applicative et proprietaire sont requises.")
    return app_url, owner_url


def _database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url, connect_timeout_seconds=2, pool_size=1, max_overflow=0, pool_timeout_seconds=2, statement_timeout_ms=10_000
    )


def _rights() -> tuple[EntitlementValue, ...]:
    return tuple(
        EntitlementValue(key, definition.kind, integer_value=1)
        if definition.kind is EntitlementKind.LIMIT
        else EntitlementValue(key, definition.kind, boolean_value=False)
        for key, definition in ENTITLEMENT_REGISTRY.items()
    )


async def test_internal_catalog_mutations_require_two_actors_and_audited_contract_transition() -> None:
    app_url, owner_url = _urls()
    app, owner = _database(app_url), _database(owner_url)
    creator, approver, organization = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    plan_id = version_id = contract_id = override_id = None
    try:
        async with owner.engine.begin() as connection:
            for user_id, label in ((creator, "creator"), (approver, "approver")):
                await connection.execute(
                    text("""
                    INSERT INTO users (id,email,email_normalized,display_name,password_hash,status,platform_role,created_at,updated_at)
                    VALUES (:id,:email,:email,:label,'hash','active','platform_admin',:now,:now)
                """),
                    {"id": user_id, "email": f"p52-{label}-{user_id}@example.ca", "label": label, "now": now},
                )
            await connection.execute(
                text("""
                INSERT INTO organizations (id,name,timezone,status,created_by,activated_at,created_at,updated_at)
                VALUES (:id,'P52 internal','America/Toronto','active',:creator,:now,:now,:now)
            """),
                {"id": organization, "creator": creator, "now": now},
            )

        async with owner.engine.connect() as connection:
            used_codes = set((await connection.scalars(text("SELECT code FROM plan_catalog"))).all())
        plan_code = next((code for code in PlanCode if code.value not in used_codes), None)
        if plan_code is None:
            pytest.skip("Les quatre codes synthétiques sont déjà réservés par une autre preuve.")
        service = CatalogAdministrationUseCases(app.catalog_audited_unit_of_work, SystemClock())
        creator_context = ActorContext(creator, "p52-03-creator")
        create_plan_command = CreateCatalogPlanCommand(plan_code, 0, operation_id=uuid4())
        plan = await service.create_plan(
            context=creator_context, command=create_plan_command, has_platform_capability=True
        )
        replayed_plan = await service.create_plan(
            context=creator_context, command=create_plan_command, has_platform_capability=True
        )
        assert replayed_plan == plan
        plan_id = plan.id
        version = await service.create_plan_version(
            context=creator_context,
            command=CreateCatalogPlanVersionCommand(plan.id, 1, CurrencyCode.CAD, "monthly", 0, now, None, _rights()),
            has_platform_capability=True,
        )
        version_id = version.id
        with pytest.raises(CatalogApprovalRequired):
            await service.publish_plan_version(
                context=creator_context, version_id=version.id, expected_version=1, has_platform_capability=True
            )
        published = await service.publish_plan_version(
            context=ActorContext(approver, "p52-03-approver"),
            version_id=version.id,
            expected_version=1,
            has_platform_capability=True,
        )
        assert published.state == "published"
        contract = await service.attach_organization_contract(
            context=ActorContext(approver, "p52-03-attach"),
            command=AttachOrganizationPlanContractCommand(organization, version.id, ContractState.ACTIVE, now, None),
            has_platform_capability=True,
        )
        contract_id = contract.id
        override_command = ProposePlanContractOverrideCommand(
            contract_id=contract.id,
            value=EntitlementValue(EntitlementKey.ACTIVE_MEMBERS_MAX, EntitlementKind.LIMIT, integer_value=2),
            justification="synthetic capacity proof",
            starts_at=now,
            ends_at=now + timedelta(days=1),
            operation_id=uuid4(),
        )
        override = await service.propose_contract_override(
            context=creator_context,
            command=override_command,
            has_platform_capability=True,
        )
        assert override.state is OverrideState.PENDING_APPROVAL
        override_id = override.id
        with pytest.raises(CatalogApprovalRequired):
            await service.approve_contract_override(
                context=creator_context,
                override_id=override.id,
                expected_version=1,
                has_platform_capability=True,
            )
        approved_override = await service.approve_contract_override(
            context=ActorContext(approver, "p52-06-approve"),
            override_id=override.id,
            expected_version=1,
            has_platform_capability=True,
        )
        assert approved_override.state is OverrideState.ACTIVE
        assert approved_override.approved_by_user_id == approver
        revoked_override = await service.revoke_contract_override(
            context=ActorContext(approver, "p52-06-revoke"),
            override_id=override.id,
            expected_version=2,
            has_platform_capability=True,
        )
        assert revoked_override.state is OverrideState.REVOKED
        assert revoked_override.version == 3
        ended = await service.change_contract_state(
            context=ActorContext(approver, "p52-03-end"),
            contract_id=contract.id,
            expected_version=1,
            state=ContractState.ENDED,
            has_platform_capability=True,
        )
        assert ended.version == 2
        assert ended.state is ContractState.ENDED
        async with owner.engine.connect() as connection:
            audit_count = await connection.scalar(
                text("""
                SELECT count(*) FROM audit_events
                WHERE entity_id IN (:plan,:version,:contract,:override)
                  AND action IN (
                    'catalog.plan_created','catalog.plan_version_created','catalog.plan_version_published',
                    'catalog.contract_attached','catalog.contract_state_changed',
                    'catalog.contract_override_proposed','catalog.contract_override_approved',
                    'catalog.contract_override_revoked'
                  )
            """),
                {"plan": plan.id, "version": version.id, "contract": contract.id, "override": override.id},
            )
        assert audit_count == 8
    finally:
        async with owner.engine.begin() as connection:
            # Le rôle propriétaire de la base de test réalise la purge contrôlée
            # des preuves d'audit avant les entités référencées. L'application,
            # elle, reste strictement append-only.
            await connection.execute(
                text(
                    "DELETE FROM audit_events "
                    "WHERE organization_id = :organization "
                    "OR actor_id IN (:creator, :approver)"
                ),
                {"organization": organization, "creator": creator, "approver": approver},
            )
            await connection.execute(
                text("DELETE FROM catalog_mutation_operations WHERE actor_id IN (:creator, :approver)"),
                {"creator": creator, "approver": approver},
            )
            if override_id:
                await connection.execute(text("DELETE FROM plan_contract_overrides WHERE id=:id"), {"id": override_id})
            if contract_id:
                await connection.execute(
                    text("DELETE FROM organization_plan_contracts WHERE id=:id"), {"id": contract_id}
                )
            if version_id:
                await connection.execute(
                    text("UPDATE plan_versions SET state='superseded' WHERE id=:id"), {"id": version_id}
                )
                await connection.execute(text("DELETE FROM plan_versions WHERE id=:id"), {"id": version_id})
            if plan_id:
                await connection.execute(text("DELETE FROM plan_catalog WHERE id=:id"), {"id": plan_id})
            await connection.execute(text("DELETE FROM organizations WHERE id=:id"), {"id": organization})
            await connection.execute(
                text("DELETE FROM users WHERE id IN (:creator, :approver)"),
                {"creator": creator, "approver": approver},
            )
        await app.close()
        await owner.close()
