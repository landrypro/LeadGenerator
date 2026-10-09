"""Preuves PostgreSQL du schéma, RLS et de l'idempotence durable P53-02."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from backend.app.application.tenancy import TenantContext
from backend.app.infrastructure.postgres import PostgresDatabase

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


async def test_billing_schema_is_tenant_isolated_and_commands_are_idempotent() -> None:
    app_url, owner_url = _urls()
    app, owner = _database(app_url), _database(owner_url)
    actor_a, actor_b, org_a, org_b, plan, version, customer_a, customer_b, subscription_a, subscription_b = (
        uuid4() for _ in range(10)
    )
    command_a, command_b, reconciliation_run = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    key_digest = "a" * 64
    fingerprint_a = "b" * 64
    fingerprint_b = "c" * 64

    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO users (id,email,email_normalized,display_name,password_hash,status,created_at,updated_at)
                    VALUES (:actor_a,:email_a,:email_a,'Billing A','hash-a','active',:now,:now),
                           (:actor_b,:email_b,:email_b,'Billing B','hash-b','active',:now,:now)
                    """
                ),
                {
                    "actor_a": actor_a,
                    "actor_b": actor_b,
                    "email_a": f"billing-a-{actor_a}@example.ca",
                    "email_b": f"billing-b-{actor_b}@example.ca",
                    "now": now,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO organizations (id,name,timezone,status,created_by,activated_at,created_at,updated_at)
                    VALUES (:org_a,'Billing A','America/Toronto','active',:actor_a,:now,:now,:now),
                           (:org_b,'Billing B','America/Toronto','active',:actor_b,:now,:now,:now)
                    """
                ),
                {"org_a": org_a, "org_b": org_b, "actor_a": actor_a, "actor_b": actor_b, "now": now},
            )
            await connection.execute(
                text("INSERT INTO plan_catalog (id,code,state) VALUES (:id,'custom','draft')"), {"id": plan}
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO plan_versions (
                      id,plan_id,version_number,state,currency,billing_cycle,amount_excluding_tax_minor,
                      effective_from,created_by_user_id,approved_by_user_id,published_at
                    ) VALUES (:id,:plan,1,'published','CAD','monthly',0,:now,:actor_a,:actor_b,:now)
                    """
                ),
                {"id": version, "plan": plan, "actor_a": actor_a, "actor_b": actor_b, "now": now},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO billing_customers (id,organization_id,provider,provider_customer_reference)
                    VALUES (:customer_a,:org_a,'simulated',:reference_a),
                           (:customer_b,:org_b,'simulated',:reference_b)
                    """
                ),
                {
                    "customer_a": customer_a,
                    "customer_b": customer_b,
                    "org_a": org_a,
                    "org_b": org_b,
                    "reference_a": f"customer-{customer_a}",
                    "reference_b": f"customer-{customer_b}",
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO subscriptions (
                      id,organization_id,billing_customer_id,provider,provider_subscription_reference,plan_version_id,
                      currency,state,current_period_start,current_period_end,provider_updated_at
                    ) VALUES
                      (:subscription_a,:org_a,:customer_a,'simulated',:reference_a,:version,
                       'CAD','pending_checkout',:now,:ends_at,:now),
                      (:subscription_b,:org_b,:customer_b,'simulated',:reference_b,:version,
                       'CAD','pending_checkout',:now,:ends_at,:now)
                    """
                ),
                {
                    "subscription_a": subscription_a,
                    "subscription_b": subscription_b,
                    "org_a": org_a,
                    "org_b": org_b,
                    "customer_a": customer_a,
                    "customer_b": customer_b,
                    "reference_a": f"subscription-{subscription_a}",
                    "reference_b": f"subscription-{subscription_b}",
                    "version": version,
                    "now": now,
                    "ends_at": now + timedelta(days=30),
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO billing_reconciliation_runs (
                      id,organization_id,run_kind,status,window_started_at,window_ended_at
                    ) VALUES (:id,:org_a,'manual','pending',:now,:ends_at)
                    """
                ),
                {"id": reconciliation_run, "org_a": org_a, "now": now, "ends_at": now + timedelta(days=30)},
            )

        context_a = TenantContext(actor_a, org_a, "billing-schema-a")
        context_b = TenantContext(actor_b, org_b, "billing-schema-b")
        async with app.tenant_unit_of_work(context_a) as unit:
            visible_to_a = await unit.session.scalar(text("SELECT count(*) FROM subscriptions"))
            reserved = await unit.session.scalar(
                text(
                    """
                    SELECT app_private.reserve_billing_command(
                      :id, 'checkout', :key_digest, :fingerprint, :now
                    )
                    """
                ),
                {"id": command_a, "key_digest": key_digest, "fingerprint": fingerprint_a, "now": now},
            )
            replayed = await unit.session.scalar(
                text(
                    """
                    SELECT app_private.reserve_billing_command(
                      :id, 'checkout', :key_digest, :fingerprint, :now
                    )
                    """
                ),
                {"id": uuid4(), "key_digest": key_digest, "fingerprint": fingerprint_a, "now": now},
            )
            conflicted = await unit.session.scalar(
                text(
                    """
                    SELECT app_private.reserve_billing_command(
                      :id, 'checkout', :key_digest, :fingerprint, :now
                    )
                    """
                ),
                {"id": uuid4(), "key_digest": key_digest, "fingerprint": fingerprint_b, "now": now},
            )
        async with app.tenant_unit_of_work(context_b) as unit:
            visible_to_b = await unit.session.scalar(text("SELECT count(*) FROM subscriptions"))
            independent_tenant_command = await unit.session.scalar(
                text(
                    """
                    SELECT app_private.reserve_billing_command(
                      :id, 'checkout', :key_digest, :fingerprint, :now
                    )
                    """
                ),
                {"id": command_b, "key_digest": key_digest, "fingerprint": fingerprint_a, "now": now},
            )
        with pytest.raises(DBAPIError):
            async with app.tenant_unit_of_work(context_a) as unit:
                await unit.session.execute(text("SELECT count(*) FROM billing_commands"))
        with pytest.raises(DBAPIError):
            async with app.tenant_unit_of_work(context_a) as unit:
                await unit.session.execute(text("SELECT count(*) FROM billing_event_inbox"))
        with pytest.raises(IntegrityError):
            async with owner.engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        INSERT INTO subscriptions (
                          organization_id,billing_customer_id,provider,provider_subscription_reference,plan_version_id,
                          currency,state,current_period_start,current_period_end,provider_updated_at
                        ) VALUES (:org_a,:customer_a,'simulated',:reference,:version,
                                  'CAD','active',:now,:ends_at,:now)
                        """
                    ),
                    {
                        "org_a": org_a,
                        "customer_a": customer_a,
                        "reference": f"second-{subscription_a}",
                        "version": version,
                        "now": now,
                        "ends_at": now + timedelta(days=30),
                    },
                )
        with pytest.raises(IntegrityError):
            async with owner.engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        INSERT INTO billing_reconciliation_differences (
                          organization_id,run_id,difference_code
                        ) VALUES (:org_b,:run_id,'unresolved')
                        """
                    ),
                    {"org_b": org_b, "run_id": reconciliation_run},
                )
        with pytest.raises(IntegrityError):
            async with owner.engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        INSERT INTO subscription_transitions (
                          organization_id,subscription_id,previous_state,next_state,cause,occurred_at
                        ) VALUES (:org_b,:subscription_a,'pending_checkout','active','invoice_paid',:now)
                        """
                    ),
                    {"org_b": org_b, "subscription_a": subscription_a, "now": now},
                )
        with pytest.raises(IntegrityError):
            async with owner.engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        INSERT INTO subscriptions (
                          organization_id,billing_customer_id,provider,provider_subscription_reference,plan_version_id,
                          currency,state,current_period_start,current_period_end,provider_updated_at
                        ) VALUES (:org_b,:customer_b,'simulated',:reference,:version,
                                  'USD','canceled',:now,:ends_at,:now)
                        """
                    ),
                    {
                        "org_b": org_b,
                        "customer_b": customer_b,
                        "reference": f"currency-{subscription_b}",
                        "version": version,
                        "now": now,
                        "ends_at": now + timedelta(days=30),
                    },
                )
        async with owner.engine.connect() as connection:
            rls = (
                (
                    await connection.execute(
                        text(
                            """
                            SELECT relname, relrowsecurity, relforcerowsecurity
                            FROM pg_class
                            WHERE relname IN (
                              'billing_customers','subscriptions','subscription_transitions','billing_commands',
                              'billing_event_inbox','billing_events','billing_reconciliation_runs',
                              'billing_reconciliation_differences','billing_refunds'
                            )
                            """
                        )
                    )
                )
                .mappings()
                .all()
            )
            policies = set(
                (
                    await connection.scalars(
                        text(
                            """
                            SELECT policyname FROM pg_policies
                            WHERE schemaname='public' AND tablename IN (
                              'billing_customers','subscriptions','subscription_transitions','billing_commands',
                              'billing_events','billing_reconciliation_runs','billing_reconciliation_differences','billing_refunds'
                            )
                            """
                        )
                    )
                ).all()
            )
            privileges = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT
                          has_table_privilege('prospect_app','public.subscriptions','SELECT') AS subscription_read,
                          has_table_privilege('prospect_app','public.billing_commands','SELECT') AS command_read,
                          has_table_privilege('prospect_app','public.billing_event_inbox','SELECT') AS inbox_read,
                          has_table_privilege('prospect_app','public.billing_reconciliation_runs','SELECT') AS reconciliation_read,
                          has_function_privilege(
                            'prospect_app',
                            'app_private.reserve_billing_command(uuid,text,text,text,timestamp with time zone)',
                            'EXECUTE'
                          ) AS reserve_execute
                        """
                        )
                    )
                )
                .mappings()
                .one()
            )
            function_metadata = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT owner_role.rolname AS owner_name, function.prosecdef, function.proconfig
                        FROM pg_proc AS function
                        JOIN pg_namespace AS namespace ON namespace.oid=function.pronamespace
                        JOIN pg_roles AS owner_role ON owner_role.oid=function.proowner
                        WHERE namespace.nspname='app_private' AND function.proname='reserve_billing_command'
                        """
                        )
                    )
                )
                .mappings()
                .one()
            )
            public_execute = await connection.scalar(
                text(
                    """
                    SELECT count(*) FROM information_schema.routine_privileges
                    WHERE routine_schema='app_private' AND routine_name='reserve_billing_command' AND grantee='PUBLIC'
                    """
                )
            )
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM billing_reconciliation_runs WHERE id=:id"), {"id": reconciliation_run}
            )
            await connection.execute(
                text("DELETE FROM billing_commands WHERE organization_id IN (:org_a,:org_b)"),
                {"org_a": org_a, "org_b": org_b},
            )
            await connection.execute(
                text("DELETE FROM subscriptions WHERE id IN (:subscription_a,:subscription_b)"),
                {"subscription_a": subscription_a, "subscription_b": subscription_b},
            )
            await connection.execute(
                text("DELETE FROM billing_customers WHERE id IN (:customer_a,:customer_b)"),
                {"customer_a": customer_a, "customer_b": customer_b},
            )
            await connection.execute(
                text("UPDATE plan_versions SET state='superseded' WHERE id=:version"), {"version": version}
            )
            await connection.execute(text("DELETE FROM plan_versions WHERE id=:version"), {"version": version})
            await connection.execute(text("DELETE FROM plan_catalog WHERE id=:plan"), {"plan": plan})
            await connection.execute(
                text("DELETE FROM organizations WHERE id IN (:org_a,:org_b)"), {"org_a": org_a, "org_b": org_b}
            )
            await connection.execute(
                text("DELETE FROM users WHERE id IN (:actor_a,:actor_b)"), {"actor_a": actor_a, "actor_b": actor_b}
            )
        await app.close()
        await owner.close()

    assert visible_to_a == 1
    assert visible_to_b == 1
    assert reserved["code"] == "reserved"
    assert replayed["code"] == "replayed"
    assert conflicted == {"code": "conflict"}
    assert independent_tenant_command["code"] == "reserved"
    assert len(rls) == 9
    assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rls)
    assert policies == {
        "billing_commands_tenant_read",
        "billing_customers_tenant_read",
        "billing_events_tenant_read",
        "billing_reconciliation_differences_tenant_read",
        "billing_reconciliation_runs_tenant_read",
        "billing_refunds_tenant_read",
        "subscription_transitions_tenant_read",
        "subscriptions_tenant_read",
    }
    assert dict(privileges) == {
        "subscription_read": True,
        "command_read": False,
        "inbox_read": False,
        "reconciliation_read": False,
        "reserve_execute": True,
    }
    assert function_metadata["owner_name"] == "prospect_rls_definer"
    assert function_metadata["prosecdef"] is True
    assert "search_path=pg_catalog, public, pg_temp" in function_metadata["proconfig"]
    assert public_execute == 0
