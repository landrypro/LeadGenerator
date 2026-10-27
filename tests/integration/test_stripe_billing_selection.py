"""DEV-02: tenant selection, pending contract, replay and isolation on PostgreSQL."""

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration


async def test_stripe_selection_is_atomic_and_tenant_scoped() -> None:
    url = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    if not url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_MIGRATION_DATABASE_URL est obligatoire.")
        pytest.skip("TEST_MIGRATION_DATABASE_URL est requis.")
    engine = create_async_engine(url)
    actor, outsider, organization, membership, plan, version, command, other_command = (uuid4() for _ in range(8))
    now = datetime.now(UTC).replace(microsecond=0)
    key = hashlib.sha256(b"dev02-initial-choice").hexdigest()
    changed_key = hashlib.sha256(b"dev02-second-choice").hexdigest()
    fingerprint = hashlib.sha256(
        json.dumps(["checkout", str(version), "subscription"], separators=(",", ":")).encode()
    ).hexdigest()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text("""
                      INSERT INTO users(id,email,email_normalized,display_name,password_hash,status,created_at,updated_at)
                      VALUES (:actor,:actor_email,:actor_email,'Billing admin','hash','active',:now,:now),
                             (:outsider,:outsider_email,:outsider_email,'Other user','hash','active',:now,:now)
                    """),
                    {
                        "actor": actor,
                        "actor_email": f"dev02-{actor}@example.test",
                        "outsider": outsider,
                        "outsider_email": f"dev02-{outsider}@example.test",
                        "now": now,
                    },
                )
                await connection.execute(
                    text("""
                      INSERT INTO organizations(id,name,locale,timezone,status,created_by,activated_at,created_at,updated_at)
                      VALUES (:organization,'DEV-02 selection','fr-CA','America/Toronto','active',:actor,:now,:now,:now)
                    """),
                    {"organization": organization, "actor": actor, "now": now},
                )
                await connection.execute(
                    text("""
                      INSERT INTO memberships(id,organization_id,user_id,role,status,created_by,updated_by,created_at,updated_at)
                      VALUES (:membership,:organization,:actor,'admin','active',:actor,:actor,:now,:now)
                    """),
                    {"membership": membership, "organization": organization, "actor": actor, "now": now},
                )
                await connection.execute(
                    text("INSERT INTO plan_catalog(id,code,state) VALUES (:plan,'custom','published')"),
                    {"plan": plan},
                )
                await connection.execute(
                    text("""
                      INSERT INTO plan_versions(id,plan_id,version_number,state,currency,billing_cycle,
                        amount_excluding_tax_minor,effective_from,created_by_user_id,approved_by_user_id,published_at)
                      VALUES (:version,:plan,1,'draft','CAD','monthly',1000,:now,:actor,:outsider,:now)
                    """),
                    {"version": version, "plan": plan, "now": now, "actor": actor, "outsider": outsider},
                )
                for entitlement, kind, integer, boolean, unit, scope in (
                    ("seats.active_members.max", "limit", 5, None, "seat", "organization"),
                    ("seats.pending_invitations.max", "limit", 5, None, "reserved_seat", "organization"),
                    ("prospects.active.max", "limit", 100, None, "prospect", "organization"),
                    ("exports.monthly.max", "limit", 10, None, "export", "period"),
                    ("imports.rows_per_run.max", "limit", 100, None, "row", "run"),
                    ("google.paid_calls.enabled", "switch", None, True, "boolean", "organization"),
                    ("automation.prepare.enabled", "switch", None, True, "boolean", "organization"),
                    ("automation.execute.enabled", "switch", None, False, "boolean", "organization"),
                ):
                    await connection.execute(
                        text("""
                          INSERT INTO plan_entitlements(plan_version_id,entitlement_key,value_kind,integer_value,
                            boolean_value,unit,scope)
                          VALUES (:version,:key,:kind,:integer,:boolean,:unit,:scope)
                        """),
                        {
                            "version": version,
                            "key": entitlement,
                            "kind": kind,
                            "integer": integer,
                            "boolean": boolean,
                            "unit": unit,
                            "scope": scope,
                        },
                    )
                await connection.execute(
                    text("UPDATE plan_versions SET state='published' WHERE id=:version"), {"version": version}
                )
                await connection.exec_driver_sql("SET LOCAL ROLE prospect_app")
                await connection.execute(
                    text("""
                      SELECT set_config('app.actor_id',:actor,true),
                             set_config('app.organization_id',:organization,true),
                             set_config('app.request_id','dev02-test',true)
                    """),
                    {"actor": str(actor), "organization": str(organization)},
                )
                parameters = {
                    "command": command,
                    "version": version,
                    "key": key,
                    "fingerprint": fingerprint,
                    "now": now,
                }
                prepare = text("""
                  SELECT app_private.prepare_stripe_sandbox_checkout_v2(
                    :command,:version,:key,:fingerprint,:now)
                """)
                initial = await connection.scalar(prepare, parameters)
                assert initial["code"] == "reserved"
                state = await connection.scalar(text("SELECT app_private.tenant_stripe_billing_state()"))
                assert state["contract"]["state"] == "pending"
                assert state["contract"]["plan_code"] == "custom"
                assert state["contract"]["version_number"] == 1
                assert state["checkout"] is None
                assert state["command"]["state"] == "reserved"

                replay = await connection.scalar(prepare, {**parameters, "command": uuid4()})
                assert replay["code"] == "replayed" and replay["command_id"] == str(command)
                second = await connection.scalar(prepare, {**parameters, "command": other_command, "key": changed_key})
                assert second["code"] == "billing_reconciliation_required"

                completion = await connection.scalar(
                    text("""
                      SELECT app_private.complete_stripe_sandbox_checkout(
                        :command,:version,'cs_test_dev02','cus_dev02','price_dev02','CAD',:expires)
                    """),
                    {"command": command, "version": version, "expires": now + timedelta(hours=1)},
                )
                assert completion["code"] == "succeeded"
                state = await connection.scalar(text("SELECT app_private.tenant_stripe_billing_state()"))
                assert state["checkout"]["state"] == "open"
                assert state["checkout"]["reference"] == "cs_test_dev02"
                assert state["command"] is None
                assert (
                    await connection.scalar(
                        text("SELECT app_private.tenant_stripe_checkout_reference(:command)"), {"command": command}
                    )
                    == "cs_test_dev02"
                )
                assert (await connection.scalar(prepare, {**parameters, "command": uuid4()}))["code"] == "replayed"
                assert (await connection.scalar(prepare, {**parameters, "command": other_command, "key": changed_key}))[
                    "code"
                ] == "billing_subscription_exists"

                await connection.execute(
                    text("SELECT set_config('app.actor_id',:actor,true)"), {"actor": str(outsider)}
                )
                assert await connection.scalar(text("SELECT app_private.tenant_stripe_billing_state()")) is None
                denied = await connection.scalar(prepare, {**parameters, "command": uuid4()})
                assert denied["code"] == "billing_capability_required"
                assert (
                    await connection.scalar(
                        text("SELECT app_private.tenant_stripe_checkout_reference(:command)"), {"command": command}
                    )
                    is None
                )
                await connection.exec_driver_sql("RESET ROLE")
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM organization_plan_contracts WHERE organization_id=:organization"),
                        {"organization": organization},
                    )
                    == 1
                )
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM billing_commands WHERE organization_id=:organization"),
                        {"organization": organization},
                    )
                    == 1
                )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
