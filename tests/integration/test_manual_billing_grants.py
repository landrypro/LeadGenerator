"""DEV-05: preuves PostgreSQL des attributions sandbox sans paiement."""

import hashlib
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration


async def test_manual_billing_grant_requires_two_platform_admins_and_never_creates_payment_artifacts() -> None:
    url = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    if not url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_MIGRATION_DATABASE_URL est obligatoire.")
        pytest.skip("TEST_MIGRATION_DATABASE_URL est requis.")

    engine = create_async_engine(url)
    requester, approver, organization, membership, plan, version, grant = (uuid4() for _ in range(7))
    now = datetime.now(UTC).replace(microsecond=0)
    key = hashlib.sha256(b"manual-grant-proposal").hexdigest()
    approve_key = hashlib.sha256(b"manual-grant-approval").hexdigest()
    revoke_key = hashlib.sha256(b"manual-grant-revocation").hexdigest()
    proposal_fingerprint = hashlib.sha256(b"manual-grant-proposal-request").hexdigest()
    approve_fingerprint = hashlib.sha256(b"manual-grant-approval-request").hexdigest()
    revoke_fingerprint = hashlib.sha256(b"manual-grant-revocation-request").hexdigest()

    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text(
                        """
                        INSERT INTO users(id,email,email_normalized,display_name,password_hash,status,platform_role,created_at,updated_at)
                        VALUES (:requester,:requester_email,:requester_email,'Requester','hash','active','platform_admin',:now,:now),
                               (:approver,:approver_email,:approver_email,'Approver','hash','active','platform_admin',:now,:now)
                        """
                    ),
                    {
                        "requester": requester,
                        "approver": approver,
                        "requester_email": f"manual-requester-{requester}@example.test",
                        "approver_email": f"manual-approver-{approver}@example.test",
                        "now": now,
                    },
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO organizations(id,name,locale,timezone,status,created_by,activated_at,created_at,updated_at)
                        VALUES (:organization,'DEV-05 manual grant','fr-CA','America/Toronto','active',:requester,:now,:now,:now)
                        """
                    ),
                    {"organization": organization, "requester": requester, "now": now},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO memberships(id,organization_id,user_id,role,status,created_by,updated_by,created_at,updated_at)
                        VALUES (:membership,:organization,:requester,'admin','active',:requester,:requester,:now,:now)
                        """
                    ),
                    {"membership": membership, "organization": organization, "requester": requester, "now": now},
                )
                await connection.execute(
                    text("INSERT INTO plan_catalog(id,code,state) VALUES (:plan,'custom','published')"),
                    {"plan": plan},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO plan_versions(
                          id,plan_id,version_number,state,currency,billing_cycle,amount_excluding_tax_minor,
                          effective_from,created_by_user_id,approved_by_user_id,published_at
                        ) VALUES (:version,:plan,1,'draft','XAF','monthly',5000,:now,:requester,:approver,:now)
                        """
                    ),
                    {"version": version, "plan": plan, "now": now, "requester": requester, "approver": approver},
                )
                for key_name, kind, integer_value, boolean_value, unit, scope in (
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
                        text(
                            """
                            INSERT INTO plan_entitlements(
                              plan_version_id,entitlement_key,value_kind,integer_value,boolean_value,unit,scope
                            ) VALUES (:version,:key_name,:kind,:integer_value,:boolean_value,:unit,:scope)
                            """
                        ),
                        {
                            "version": version,
                            "key_name": key_name,
                            "kind": kind,
                            "integer_value": integer_value,
                            "boolean_value": boolean_value,
                            "unit": unit,
                            "scope": scope,
                        },
                    )
                await connection.execute(
                    text("UPDATE plan_versions SET state='published' WHERE id=:version"), {"version": version}
                )

                await connection.exec_driver_sql("SET LOCAL ROLE prospect_app")
                await connection.execute(
                    text(
                        "SELECT set_config('app.actor_id',:actor,true),set_config('app.request_id','dev05-test',true)"
                    ),
                    {"actor": str(requester)},
                )
                propose = text(
                    """
                    SELECT app_private.propose_platform_manual_billing_grant(
                      :grant,:operation,:key,:fingerprint,:organization,:version,'sandbox_validation',31,:now)
                    """
                )
                created = await connection.scalar(
                    propose,
                    {
                        "grant": grant,
                        "operation": uuid4(),
                        "key": key,
                        "fingerprint": proposal_fingerprint,
                        "organization": organization,
                        "version": version,
                        "now": now,
                    },
                )
                replay = await connection.scalar(
                    propose,
                    {
                        "grant": uuid4(),
                        "operation": uuid4(),
                        "key": key,
                        "fingerprint": proposal_fingerprint,
                        "organization": organization,
                        "version": version,
                        "now": now,
                    },
                )
                self_approval = await connection.scalar(
                    text(
                        """
                        SELECT app_private.approve_platform_manual_billing_grant(
                          :grant,:operation,:key,:fingerprint,1,:now)
                        """
                    ),
                    {
                        "grant": grant,
                        "operation": uuid4(),
                        "key": approve_key,
                        "fingerprint": approve_fingerprint,
                        "now": now,
                    },
                )

                await connection.execute(
                    text("SELECT set_config('app.actor_id',:actor,true)"), {"actor": str(approver)}
                )
                approved = await connection.scalar(
                    text(
                        """
                        SELECT app_private.approve_platform_manual_billing_grant(
                          :grant,:operation,:key,:fingerprint,1,:now)
                        """
                    ),
                    {
                        "grant": grant,
                        "operation": uuid4(),
                        "key": approve_key,
                        "fingerprint": approve_fingerprint,
                        "now": now,
                    },
                )

                await connection.execute(
                    text(
                        "SELECT set_config('app.actor_id',:actor,true),set_config('app.organization_id',:organization,true)"
                    ),
                    {"actor": str(requester), "organization": str(organization)},
                )
                entitlement = await connection.scalar(
                    text("SELECT app_private.tenant_effective_entitlement('seats.active_members.max',:now)"),
                    {"now": now},
                )
                checkout = await connection.scalar(
                    text(
                        """
                        SELECT app_private.prepare_stripe_sandbox_checkout_v2(
                          :command,:version,:key,:fingerprint,:now)
                        """
                    ),
                    {
                        "command": uuid4(),
                        "version": version,
                        "key": hashlib.sha256(b"manual-grant-checkout").hexdigest(),
                        "fingerprint": hashlib.sha256(b"manual-grant-checkout-request").hexdigest(),
                        "now": now,
                    },
                )

                await connection.execute(
                    text("SELECT set_config('app.actor_id',:actor,true)"), {"actor": str(approver)}
                )
                revoked = await connection.scalar(
                    text(
                        """
                        SELECT app_private.revoke_platform_manual_billing_grant(
                          :grant,:operation,:key,:fingerprint,2,:now)
                        """
                    ),
                    {
                        "grant": grant,
                        "operation": uuid4(),
                        "key": revoke_key,
                        "fingerprint": revoke_fingerprint,
                        "now": now,
                    },
                )
                await connection.exec_driver_sql("RESET ROLE")
                payment_artifacts = await connection.execute(
                    text(
                        """
                        SELECT
                          (SELECT count(*) FROM billing_customers WHERE organization_id=:organization),
                          (SELECT count(*) FROM billing_commands WHERE organization_id=:organization),
                          (SELECT count(*) FROM subscriptions WHERE organization_id=:organization),
                          (SELECT count(*) FROM organization_plan_contracts WHERE organization_id=:organization)
                        """
                    ),
                    {"organization": organization},
                )
                counts = payment_artifacts.one()
                operation_count = await connection.scalar(
                    text("SELECT count(*) FROM manual_billing_grant_operations WHERE grant_id=:grant"), {"grant": grant}
                )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()

    assert created["code"] == "created"
    assert replay["code"] == "replayed"
    assert replay["grant"]["id"] == str(grant)
    assert self_approval["code"] == "approval_required"
    assert approved["code"] == "approved"
    assert approved["grant"]["state"] == "active"
    assert entitlement["code"] == "allowed"
    assert entitlement["source"] == "manual_grant"
    assert entitlement["integer_value"] == 5
    assert checkout["code"] == "billing_subscription_exists"
    assert revoked["code"] == "revoked"
    assert tuple(counts) == (0, 0, 0, 0)
    assert operation_count == 3
