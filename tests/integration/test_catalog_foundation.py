"""Preuves PostgreSQL du socle P5.2, exécutées uniquement avec les services réels."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.application.tenancy import TenantContext
from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.catalog_reader import SqlAlchemyOrganizationCatalogReader

pytestmark = pytest.mark.integration


def _urls() -> tuple[str, str]:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not app_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("Les URL PostgreSQL applicative et proprietaire sont requises.")
    return app_url, owner_url


def _database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=2,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=10_000,
    )


async def test_catalog_entitlements_are_tenant_isolated_and_fail_closed() -> None:
    app_url, owner_url = _urls()
    app, owner = _database(app_url), _database(owner_url)
    org_a, org_b, actor_a, actor_b, approver = (uuid4() for _ in range(5))
    plan, version, contract_a, contract_b, override = (uuid4() for _ in range(5))
    now = datetime.now(UTC).replace(microsecond=0)
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO users (id,email,email_normalized,display_name,password_hash,status,created_at,updated_at)
                    VALUES (:actor_a,:email_a,:email_a,'A','hash-a','active',:now,:now),
                           (:actor_b,:email_b,:email_b,'B','hash-b','active',:now,:now),
                           (:approver,:email_c,:email_c,'C','hash-c','active',:now,:now)
                    """
                ),
                {
                    "actor_a": actor_a,
                    "actor_b": actor_b,
                    "approver": approver,
                    "email_a": f"catalog-a-{actor_a}@example.ca",
                    "email_b": f"catalog-b-{actor_b}@example.ca",
                    "email_c": f"catalog-c-{approver}@example.ca",
                    "now": now,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO organizations (id,name,timezone,status,created_by,activated_at,created_at,updated_at)
                    VALUES (:org_a,'Catalogue A','America/Toronto','active',:actor_a,:now,:now,:now),
                           (:org_b,'Catalogue B','America/Toronto','active',:actor_b,:now,:now,:now)
                    """
                ),
                {"org_a": org_a, "org_b": org_b, "actor_a": actor_a, "actor_b": actor_b, "now": now},
            )
            await connection.execute(
                text("INSERT INTO plan_catalog (id,code,state) VALUES (:plan,'freemium','draft')"), {"plan": plan}
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO plan_versions (
                      id,plan_id,version_number,state,currency,billing_cycle,amount_excluding_tax_minor,
                      effective_from,created_by_user_id,approved_by_user_id,published_at
                    ) VALUES (:version,:plan,1,'draft','CAD','monthly',0,:now,:actor_a,:approver,:now)
                    """
                ),
                {"version": version, "plan": plan, "actor_a": actor_a, "approver": approver, "now": now},
            )
            for key, kind, integer, boolean, unit_name, scope in (
                ("seats.active_members.max", "limit", 5, None, "seat", "organization"),
                ("seats.pending_invitations.max", "limit", 5, None, "reserved_seat", "organization"),
                ("prospects.active.max", "limit", 50, None, "prospect", "organization"),
                ("exports.monthly.max", "limit", 5, None, "export", "period"),
                ("imports.rows_per_run.max", "limit", 100, None, "row", "run"),
                ("google.paid_calls.enabled", "switch", None, False, "boolean", "organization"),
                ("automation.prepare.enabled", "switch", None, False, "boolean", "organization"),
                ("automation.execute.enabled", "switch", None, False, "boolean", "organization"),
            ):
                await connection.execute(
                    text(
                        """
                        INSERT INTO plan_entitlements
                          (id,plan_version_id,entitlement_key,value_kind,integer_value,boolean_value,unit,scope)
                        VALUES (:id,:version,:key,:kind,:integer,:boolean,:unit,:scope)
                        """
                    ),
                    {
                        "id": uuid4(),
                        "version": version,
                        "key": key,
                        "kind": kind,
                        "integer": integer,
                        "boolean": boolean,
                        "unit": unit_name,
                        "scope": scope,
                    },
                )
            await connection.execute(
                text("UPDATE plan_versions SET state='published' WHERE id=:version"), {"version": version}
            )
            for contract, organization, actor in ((contract_a, org_a, actor_a), (contract_b, org_b, actor_b)):
                await connection.execute(
                    text(
                        """
                        INSERT INTO organization_plan_contracts
                          (id,organization_id,plan_version_id,state,currency,effective_from,created_by_user_id,updated_by_user_id)
                        VALUES (:contract,:organization,:version,'active','CAD',:now,:actor,:actor)
                        """
                    ),
                    {
                        "contract": contract,
                        "organization": organization,
                        "version": version,
                        "now": now,
                        "actor": actor,
                    },
                )
            await connection.execute(
                text(
                    """
                    INSERT INTO plan_contract_overrides
                      (id,organization_id,contract_id,entitlement_key,value_kind,integer_value,boolean_value,state,
                       justification,requested_by_user_id,approved_by_user_id,starts_at,ends_at)
                    VALUES (:override,:organization,:contract,'seats.active_members.max','limit',7,NULL,'active',
                      'preuve P52-04',:requested_by,:approved_by,:starts_at,:ends_at)
                    """
                ),
                {
                    "override": override,
                    "organization": org_a,
                    "contract": contract_a,
                    "requested_by": actor_a,
                    "approved_by": approver,
                    "starts_at": now - timedelta(hours=1),
                    "ends_at": now + timedelta(hours=1),
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO entitlement_safety_ceilings
                      (entitlement_key,value_kind,integer_value,boolean_value)
                    VALUES ('seats.active_members.max','limit',6,NULL)
                    """
                )
            )

        context_a = TenantContext(actor_a, org_a, "catalog-proof-a")
        context_b = TenantContext(actor_b, org_b, "catalog-proof-b")
        reader = SqlAlchemyOrganizationCatalogReader(app.tenant_unit_of_work)
        async with app.tenant_unit_of_work(context_a) as unit:
            visible_to_a = await unit.session.scalar(text("SELECT count(*) FROM organization_plan_contracts"))
            decision_a = await unit.session.scalar(
                text("SELECT app_private.tenant_effective_entitlement('seats.active_members.max', :now)"), {"now": now}
            )
            decision_a_plan = await unit.session.scalar(
                text("SELECT app_private.tenant_effective_entitlement('exports.monthly.max', :now)"), {"now": now}
            )
        async with app.tenant_unit_of_work(context_b) as unit:
            visible_to_b = await unit.session.scalar(text("SELECT count(*) FROM organization_plan_contracts"))
            decision_b = await unit.session.scalar(
                text("SELECT app_private.tenant_effective_entitlement('google.paid_calls.enabled', :now)"), {"now": now}
            )
        catalog_a = await reader.get_current(context=context_a, now=now)
        catalog_b = await reader.get_current(context=context_b, now=now)
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM entitlement_safety_ceilings WHERE entitlement_key='seats.active_members.max'")
            )
            await connection.execute(
                text("DELETE FROM plan_contract_overrides WHERE id=:override"), {"override": override}
            )
            await connection.execute(
                text("DELETE FROM organization_plan_contracts WHERE id IN (:contract_a, :contract_b)"),
                {"contract_a": contract_a, "contract_b": contract_b},
            )
            await connection.execute(
                text("UPDATE plan_versions SET state='superseded' WHERE id=:version"), {"version": version}
            )
            await connection.execute(text("DELETE FROM plan_versions WHERE id=:version"), {"version": version})
            await connection.execute(text("DELETE FROM plan_catalog WHERE id=:plan"), {"plan": plan})
            await connection.execute(
                text("DELETE FROM organizations WHERE id IN (:org_a, :org_b)"), {"org_a": org_a, "org_b": org_b}
            )
            await connection.execute(
                text("DELETE FROM users WHERE id IN (:actor_a, :actor_b, :approver)"),
                {"actor_a": actor_a, "actor_b": actor_b, "approver": approver},
            )
        await app.close()
        await owner.close()

    assert visible_to_a == 1
    assert visible_to_b == 1
    assert decision_a["code"] == "safety_ceiling_exceeded"
    assert decision_a["reason"] == "safety_ceiling_exceeded"
    assert "integer_value" not in decision_a
    assert "boolean_value" not in decision_a
    assert [item["source"] for item in decision_a["provenance"]] == [
        "contract",
        "plan_version",
        "override",
        "safety_ceiling",
    ]
    assert decision_a_plan["code"] == "allowed"
    assert decision_a_plan["source"] == "plan_version"
    assert decision_b["code"] == "entitlement_disabled"
    assert decision_b["boolean_value"] is False
    assert catalog_a.contract is not None and catalog_a.contract.id == contract_a
    assert catalog_b.contract is not None and catalog_b.contract.id == contract_b
    assert len(catalog_a.entitlements) == 8
    active_members = next(item for item in catalog_a.entitlements if item.key.value == "seats.active_members.max")
    assert active_members.code == "safety_ceiling_exceeded"
    assert active_members.integer_value is None


async def test_published_catalog_version_refuses_a_commercial_value_change() -> None:
    """P52-CAT-02 : une version publiée reste un historique immuable."""

    app_url, owner_url = _urls()
    app, owner = _database(app_url), _database(owner_url)
    actor, approver, plan, version = (uuid4() for _ in range(4))
    now = datetime.now(UTC).replace(microsecond=0)
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO users (id,email,email_normalized,display_name,password_hash,status,created_at,updated_at)
                    VALUES (:actor,:actor_email,:actor_email,'Actor','hash','active',:now,:now),
                           (:approver,:approver_email,:approver_email,'Approver','hash','active',:now,:now)
                    """
                ),
                {
                    "actor": actor,
                    "approver": approver,
                    "actor_email": f"p52-immutability-{actor}@example.ca",
                    "approver_email": f"p52-immutability-{approver}@example.ca",
                    "now": now,
                },
            )
            await connection.execute(
                text("INSERT INTO plan_catalog (id,code,state) VALUES (:plan,'starter','draft')"), {"plan": plan}
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO plan_versions (
                      id,plan_id,version_number,state,currency,billing_cycle,amount_excluding_tax_minor,
                      effective_from,created_by_user_id,approved_by_user_id,published_at
                    ) VALUES (:version,:plan,1,'draft','CAD','monthly',17,:now,:actor,:approver,:now)
                    """
                ),
                {"version": version, "plan": plan, "actor": actor, "approver": approver, "now": now},
            )
            for key, kind, integer, boolean, unit_name, scope in (
                ("seats.active_members.max", "limit", 5, None, "seat", "organization"),
                ("seats.pending_invitations.max", "limit", 5, None, "reserved_seat", "organization"),
                ("prospects.active.max", "limit", 50, None, "prospect", "organization"),
                ("exports.monthly.max", "limit", 5, None, "export", "period"),
                ("imports.rows_per_run.max", "limit", 100, None, "row", "run"),
                ("google.paid_calls.enabled", "switch", None, False, "boolean", "organization"),
                ("automation.prepare.enabled", "switch", None, False, "boolean", "organization"),
                ("automation.execute.enabled", "switch", None, False, "boolean", "organization"),
            ):
                await connection.execute(
                    text(
                        """
                        INSERT INTO plan_entitlements
                          (id,plan_version_id,entitlement_key,value_kind,integer_value,boolean_value,unit,scope)
                        VALUES (:id,:version,:key,:kind,:integer,:boolean,:unit,:scope)
                        """
                    ),
                    {
                        "id": uuid4(),
                        "version": version,
                        "key": key,
                        "kind": kind,
                        "integer": integer,
                        "boolean": boolean,
                        "unit": unit_name,
                        "scope": scope,
                    },
                )
            await connection.execute(
                text("UPDATE plan_versions SET state='published' WHERE id=:version"), {"version": version}
            )

        with pytest.raises(SQLAlchemyError):
            async with owner.engine.begin() as connection:
                await connection.execute(
                    text("UPDATE plan_versions SET amount_excluding_tax_minor=18 WHERE id=:version"),
                    {"version": version},
                )

        async with owner.engine.connect() as connection:
            amount = await connection.scalar(
                text("SELECT amount_excluding_tax_minor FROM plan_versions WHERE id=:version"), {"version": version}
            )
        assert amount == 17
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("UPDATE plan_versions SET state='superseded' WHERE id=:version"), {"version": version}
            )
            await connection.execute(text("DELETE FROM plan_versions WHERE id=:version"), {"version": version})
            await connection.execute(text("DELETE FROM plan_catalog WHERE id=:plan"), {"plan": plan})
            await connection.execute(
                text("DELETE FROM users WHERE id IN (:actor,:approver)"), {"actor": actor, "approver": approver}
            )
        await app.close()
        await owner.close()
