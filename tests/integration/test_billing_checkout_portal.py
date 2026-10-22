"""Preuves P53-06 : idempotence concurrente et sélection commerciale serveur."""

import asyncio
import importlib
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.application.errors import BillingOperationError
from backend.app.application.ports.billing import BillingReturnTarget
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.billing import BillingSessionUseCases
from backend.app.domain.billing import BillingErrorCode
from backend.app.infrastructure.billing.simulated import SimulatedBillingProviderGateway
from backend.app.infrastructure.clock import SystemClock
from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.billing_commands import SqlAlchemyBillingCommandRepository

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
        pool_size=3,
        max_overflow=0,
        pool_timeout_seconds=3,
        statement_timeout_ms=10_000,
    )


@pytest.mark.parametrize("currency", ["CAD", "USD", "EUR", "XAF"])
async def test_concurrent_checkout_and_portal_are_durable_idempotent_and_minimized(
    currency: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_url, owner_url = _urls()
    app, owner = _database(app_url), _database(owner_url)
    actor, approver, organization, membership, plan, plan_version = (uuid4() for _ in range(6))
    now = datetime.now(UTC).replace(microsecond=0)
    context = TenantContext(actor, organization, "p53-06-integration")
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO users (id,email,email_normalized,display_name,password_hash,status,created_at,updated_at)
                    VALUES (:actor,:actor_email,:actor_email,'Billing admin','hash','active',:now,:now),
                           (:approver,:approver_email,:approver_email,'Billing approval','hash','active',:now,:now)
                    """
                ),
                {
                    "actor": actor,
                    "approver": approver,
                    "actor_email": f"billing-{actor}@example.test",
                    "approver_email": f"billing-{approver}@example.test",
                    "now": now,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO organizations (id,name,locale,timezone,status,created_by,activated_at,created_at,updated_at)
                    VALUES (:organization,'Billing P53-06','fr-CA','America/Toronto','active',:actor,:now,:now,:now)
                    """
                ),
                {"organization": organization, "actor": actor, "now": now},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO memberships
                      (id,organization_id,user_id,role,status,created_by,updated_by,created_at,updated_at)
                    VALUES (:membership,:organization,:actor,'admin','active',:actor,:actor,:now,:now)
                    """
                ),
                {
                    "membership": membership,
                    "organization": organization,
                    "actor": actor,
                    "now": now,
                },
            )
            await connection.execute(
                text("INSERT INTO plan_catalog (id,code,state) VALUES (:plan,'custom','published')"),
                {"plan": plan},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO plan_versions (
                      id,plan_id,version_number,state,currency,billing_cycle,amount_excluding_tax_minor,
                      effective_from,created_by_user_id,approved_by_user_id,published_at
                    ) VALUES (:version,:plan,1,'draft',:currency,'monthly',4900,:now,:actor,:approver,:now)
                    """
                ),
                {
                    "version": plan_version,
                    "currency": currency,
                    "plan": plan,
                    "actor": actor,
                    "approver": approver,
                    "now": now,
                },
            )
            entitlements = (
                ("seats.active_members.max", "limit", 5, None, "seat", "organization"),
                ("seats.pending_invitations.max", "limit", 5, None, "reserved_seat", "organization"),
                ("prospects.active.max", "limit", 100, None, "prospect", "organization"),
                ("exports.monthly.max", "limit", 10, None, "export", "period"),
                ("imports.rows_per_run.max", "limit", 100, None, "row", "run"),
                ("google.paid_calls.enabled", "switch", None, True, "boolean", "organization"),
                ("automation.prepare.enabled", "switch", None, True, "boolean", "organization"),
                ("automation.execute.enabled", "switch", None, False, "boolean", "organization"),
            )
            for key, kind, integer, boolean, unit_name, scope in entitlements:
                await connection.execute(
                    text(
                        """
                        INSERT INTO plan_entitlements
                          (plan_version_id,entitlement_key,value_kind,integer_value,boolean_value,unit,scope)
                        VALUES (:version,:key,:kind,:integer,:boolean,:unit,:scope)
                        """
                    ),
                    {
                        "version": plan_version,
                        "key": key,
                        "kind": kind,
                        "integer": integer,
                        "boolean": boolean,
                        "unit": unit_name,
                        "scope": scope,
                    },
                )
            await connection.execute(
                text("UPDATE plan_versions SET state='published' WHERE id=:version"), {"version": plan_version}
            )

        provider = SimulatedBillingProviderGateway(
            webhook_secret=b"p53-06-integration-secret-at-least-32-bytes",
            clock=lambda: now,
        )
        service = BillingSessionUseCases(
            SqlAlchemyBillingCommandRepository(app.tenant_unit_of_work), provider, SystemClock()
        )
        checkout_args = {
            "context": context,
            "plan_version_id": plan_version,
            "idempotency_key": "concurrent-checkout",
            "return_target": BillingReturnTarget.SUBSCRIPTION,
            "authorized": True,
            "session_issued_at": now,
        }
        first, second = await asyncio.gather(
            service.create_checkout(**checkout_args), service.create_checkout(**checkout_args)
        )
        with pytest.raises(BillingOperationError) as changed_version:
            await service.create_checkout(**{**checkout_args, "plan_version_id": uuid4()})
        assert changed_version.value.code is BillingErrorCode.COMMAND_CONFLICT
        with pytest.raises(BillingOperationError) as reused_key:
            await service.create_portal(
                context=context,
                idempotency_key="concurrent-checkout",
                return_target=BillingReturnTarget.SUBSCRIPTION,
                authorized=True,
                session_issued_at=now,
            )
        portal = await service.create_portal(
            context=context,
            idempotency_key="portal-once",
            return_target=BillingReturnTarget.SUBSCRIPTION,
            authorized=True,
            session_issued_at=now,
        )

        async with owner.engine.connect() as connection:
            counts = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT
                          (SELECT count(*) FROM billing_commands WHERE organization_id=:organization) AS commands,
                          (SELECT count(*) FROM billing_customers WHERE organization_id=:organization) AS customers,
                          (SELECT count(*) FROM subscriptions WHERE organization_id=:organization) AS subscriptions,
                          (SELECT count(*) FROM audit_events WHERE organization_id=:organization
                            AND action IN (
                              'billing.checkout_requested','billing.checkout_session_created',
                              'billing.portal_requested','billing.portal_session_created'
                            )) AS audits
                        """
                        ),
                        {"organization": organization},
                    )
                )
                .mappings()
                .one()
            )
            stored_currency = await connection.scalar(
                text("SELECT currency FROM subscriptions WHERE organization_id=:organization"),
                {"organization": organization},
            )
            command_id = await connection.scalar(
                text("SELECT id FROM billing_commands WHERE organization_id=:organization AND command_kind='checkout'"),
                {"organization": organization},
            )
        async with app.tenant_unit_of_work(context) as unit:
            bad_currency = "USD" if currency == "CAD" else "CAD"
            params = {
                "command": command_id,
                "version": plan_version,
                "currency": bad_currency,
                "price": f"sim_price_{str(plan_version).replace('-', '')}",
                "now": now,
                "end": now + timedelta(days=30),
            }
            rejected = await unit.session.scalar(
                text(
                    """
                    SELECT app_private.complete_billing_checkout(
                      :command,:version,'simulated','fake-checkout','fake-customer','fake-subscription',
                      :currency,:price,:now,:end,:now
                    )
                    """
                ),
                params,
            )
            assert rejected["code"] == "billing_catalog_version_unavailable"
            params["currency"] = currency
            params["price"] = "sim_price_forged"
            rejected_price = await unit.session.scalar(
                text(
                    """
                    SELECT app_private.complete_billing_checkout(
                      :command,:version,'simulated','fake-checkout','fake-customer','fake-subscription',
                      :currency,:price,:now,:end,:now
                    )
                    """
                ),
                params,
            )
            assert rejected_price["code"] == "billing_catalog_version_unavailable"
            params["version"] = uuid4()
            rejected_version = await unit.session.scalar(
                text(
                    """
                    SELECT app_private.complete_billing_checkout(
                      :command,:version,'simulated','fake-checkout','fake-customer','fake-subscription',
                      :currency,:price,:now,:end,:now
                    )
                    """
                ),
                params,
            )
            assert rejected_version["code"] == "billing_command_conflict"

        migration = importlib.import_module(
            "backend.app.infrastructure.postgres.migrations.versions.20261021_0056_billing_checkout_multicurrency"
        )
        statements: list[str] = []

        class CaptureOperations:
            def execute(self, statement: str) -> None:
                statements.append(statement)

        with monkeypatch.context() as patch:
            patch.setattr(migration, "op", CaptureOperations())
            migration.downgrade()
            downgrade_statements = list(statements)
            statements.clear()
            migration.upgrade()
            upgrade_statements = list(statements)

        # DDL PostgreSQL transactionnel : ne jamais modifier durablement la base de recette.
        async with owner.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.exec_driver_sql(downgrade_statements[0])
                if currency != "CAD":
                    with pytest.raises(SQLAlchemyError, match="P53-06B rollback blocked"):
                        await connection.exec_driver_sql(downgrade_statements[1])
                else:
                    for statement in downgrade_statements[1:] + upgrade_statements:
                        await connection.exec_driver_sql(statement)
            finally:
                await transaction.rollback()
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(text("DELETE FROM audit_events WHERE organization_id=:id"), {"id": organization})
            await connection.execute(text("DELETE FROM subscriptions WHERE organization_id=:id"), {"id": organization})
            await connection.execute(
                text("DELETE FROM billing_customers WHERE organization_id=:id"), {"id": organization}
            )
            await connection.execute(
                text("DELETE FROM billing_commands WHERE organization_id=:id"), {"id": organization}
            )
            await connection.execute(text("DELETE FROM memberships WHERE id=:id"), {"id": membership})
            await connection.execute(
                text("UPDATE plan_versions SET state='superseded' WHERE id=:id"), {"id": plan_version}
            )
            await connection.execute(text("DELETE FROM plan_versions WHERE id=:id"), {"id": plan_version})
            await connection.execute(text("DELETE FROM plan_catalog WHERE id=:id"), {"id": plan})
            await connection.execute(text("DELETE FROM organizations WHERE id=:id"), {"id": organization})
            await connection.execute(
                text("DELETE FROM users WHERE id IN (:actor,:approver)"), {"actor": actor, "approver": approver}
            )
        await app.close()
        await owner.close()

    assert first == second
    assert stored_currency == currency
    assert reused_key.value.code is BillingErrorCode.COMMAND_CONFLICT
    assert first.url.startswith("http://billing-simulator.local/checkout/")
    assert portal.url.startswith("http://billing-simulator.local/portal/")
    assert dict(counts) == {"commands": 2, "customers": 1, "subscriptions": 1, "audits": 4}
