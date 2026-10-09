"""Preuves PostgreSQL réelles des réservations de sièges P52-05."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from backend.app.application.tenancy import InvitationAcceptanceContext, TenantContext
from backend.app.infrastructure.postgres import PostgresDatabase

pytestmark = pytest.mark.integration


def _urls() -> tuple[str, str]:
    app_url, owner_url = os.environ.get("TEST_DATABASE_URL", ""), os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not app_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("Les URL PostgreSQL applicative et proprietaire sont requises.")
    return app_url, owner_url


def _database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url, connect_timeout_seconds=2, pool_size=3, max_overflow=0, pool_timeout_seconds=2, statement_timeout_ms=10_000
    )


async def _seed(owner: PostgresDatabase, now: datetime) -> tuple[UUID, UUID, UUID, UUID, UUID]:
    organization, admin, approver, plan, version = (uuid4() for _ in range(5))
    async with owner.engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO users (id,email,email_normalized,display_name,password_hash,status,created_at,updated_at)
                VALUES (:admin,:admin_email,:admin_email,'Admin','hash','active',:now,:now),
                       (:approver,:approver_email,:approver_email,'Approver','hash','active',:now,:now)
                """
            ),
            {
                "admin": admin,
                "approver": approver,
                "admin_email": f"seat-admin-{admin}@example.ca",
                "approver_email": f"seat-approver-{approver}@example.ca",
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO organizations (id,name,timezone,status,created_by,activated_at,created_at,updated_at)
                VALUES (:organization,'Sièges','America/Toronto','active',:admin,:now,:now,:now)
                """
            ),
            {"organization": organization, "admin": admin, "now": now},
        )
        await connection.execute(
            text(
                """
                INSERT INTO memberships (id,organization_id,user_id,role,status,created_by,updated_by,created_at,updated_at,version)
                VALUES (:membership,:organization,:admin,'admin','active',:admin,:admin,:now,:now,1)
                """
            ),
            {"organization": organization, "admin": admin, "membership": uuid4(), "now": now},
        )
        await connection.execute(
            text(
                """
                INSERT INTO plan_catalog (id,code,state) VALUES (:plan,'freemium','draft');
                """
            ),
            {"plan": plan},
        )
        await connection.execute(
            text(
                """
                INSERT INTO plan_versions (id,plan_id,version_number,state,currency,billing_cycle,amount_excluding_tax_minor,effective_from,created_by_user_id,approved_by_user_id,published_at)
                VALUES (:version,:plan,1,'draft','CAD','monthly',0,:now,:admin,:approver,:now)
                """
            ),
            {
                "admin": admin,
                "plan": plan,
                "version": version,
                "approver": approver,
                "now": now,
            },
        )
        for key, kind, integer, boolean, unit, scope in (
            ("seats.active_members.max", "limit", 2, None, "seat", "organization"),
            ("seats.pending_invitations.max", "limit", 2, None, "reserved_seat", "organization"),
            ("prospects.active.max", "limit", 50, None, "prospect", "organization"),
            ("exports.monthly.max", "limit", 5, None, "export", "period"),
            ("imports.rows_per_run.max", "limit", 100, None, "row", "run"),
            ("google.paid_calls.enabled", "switch", None, False, "boolean", "organization"),
            ("automation.prepare.enabled", "switch", None, False, "boolean", "organization"),
            ("automation.execute.enabled", "switch", None, False, "boolean", "organization"),
        ):
            await connection.execute(
                text(
                    """INSERT INTO plan_entitlements (id,plan_version_id,entitlement_key,value_kind,integer_value,boolean_value,unit,scope)
                       VALUES (:id,:version,:key,:kind,:integer,:boolean,:unit,:scope)"""
                ),
                {
                    "id": uuid4(),
                    "version": version,
                    "key": key,
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
        await connection.execute(
            text(
                """INSERT INTO organization_plan_contracts (id,organization_id,plan_version_id,state,currency,effective_from,created_by_user_id,updated_by_user_id)
                   VALUES (:id,:organization,:version,'active','CAD',:now,:admin,:admin)"""
            ),
            {"id": uuid4(), "organization": organization, "version": version, "admin": admin, "now": now},
        )
    return organization, admin, approver, plan, version


async def _create(app: PostgresDatabase, organization: UUID, admin: UUID, email: str, now: datetime) -> dict[str, Any]:
    token_hash = uuid4().hex + uuid4().hex
    async with app.tenant_unit_of_work(TenantContext(admin, organization, str(uuid4()))) as unit:
        payload = await unit.session.scalar(
            text(
                """SELECT app_private.tenant_create_member_invitation_audited(
                  :invitation,:attempt,:email,:email,'sales',:request,:token,:expires,:now)"""
            ),
            {
                "invitation": uuid4(),
                "attempt": uuid4(),
                "email": email,
                "request": uuid4(),
                "token": token_hash,
                "expires": now + timedelta(hours=1),
                "now": now,
            },
        )
        await unit.commit()
    return dict(payload)


async def _cleanup(
    owner: PostgresDatabase, organization: UUID, admin: UUID, approver: UUID, plan: UUID, version: UUID
) -> None:
    async with owner.engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM audit_events WHERE organization_id=:organization"), {"organization": organization}
        )
        await connection.execute(
            text("DELETE FROM plan_contract_overrides WHERE organization_id=:organization"),
            {"organization": organization},
        )
        await connection.execute(
            text("DELETE FROM invitation_delivery_attempts WHERE organization_id=:organization"),
            {"organization": organization},
        )
        await connection.execute(
            text("DELETE FROM user_invitations WHERE organization_id=:organization"), {"organization": organization}
        )
        await connection.execute(
            text("DELETE FROM organization_plan_contracts WHERE organization_id=:organization"),
            {"organization": organization},
        )
        await connection.execute(
            text("UPDATE plan_versions SET state='superseded' WHERE id=:version"), {"version": version}
        )
        await connection.execute(text("DELETE FROM plan_versions WHERE id=:version"), {"version": version})
        await connection.execute(text("DELETE FROM plan_catalog WHERE id=:plan"), {"plan": plan})
        await connection.execute(
            text("DELETE FROM organizations WHERE id=:organization"), {"organization": organization}
        )
        await connection.execute(
            text("DELETE FROM users WHERE id IN (:admin,:approver)"), {"admin": admin, "approver": approver}
        )


async def test_seat_reservation_is_atomic_and_an_expired_reservation_is_reusable() -> None:
    app_url, owner_url = _urls()
    app, owner = _database(app_url), _database(owner_url)
    now = datetime.now(UTC).replace(microsecond=0)
    organization = admin = approver = plan = version = None
    try:
        organization, admin, approver, plan, version = await _seed(owner, now)
        first, second = await asyncio.gather(
            _create(app, organization, admin, "first@example.ca", now),
            _create(app, organization, admin, "second@example.ca", now),
        )
        assert sorted(str(item["code"]) for item in (first, second)) == ["created", "seat_limit_reached"]
        reused = await _create(app, organization, admin, "third@example.ca", now + timedelta(hours=2))
        assert reused["code"] == "created"
        async with owner.engine.connect() as connection:
            pending = await connection.scalar(
                text(
                    """SELECT count(*) FROM user_invitations
                       WHERE organization_id=:organization AND revoked_at IS NULL AND expires_at > :now"""
                ),
                {"organization": organization, "now": now + timedelta(hours=2)},
            )
        assert pending == 1
    finally:
        if (
            organization is not None
            and admin is not None
            and approver is not None
            and plan is not None
            and version is not None
        ):
            await _cleanup(owner, organization, admin, approver, plan, version)
        await app.close()
        await owner.close()


async def test_seat_acceptance_is_revalidated_and_last_administrator_is_protected() -> None:
    app_url, owner_url = _urls()
    app, owner = _database(app_url), _database(owner_url)
    now = datetime.now(UTC).replace(microsecond=0)
    organization = admin = approver = plan = version = None
    try:
        organization, admin, approver, plan, version = await _seed(owner, now)
        invitation = await _create(app, organization, admin, "accept@example.ca", now)
        assert invitation["code"] == "created"
        invitation_id = invitation["view"]["invitation_id"]
        async with owner.engine.begin() as connection:
            contract = await connection.scalar(
                text("SELECT id FROM organization_plan_contracts WHERE organization_id=:organization"),
                {"organization": organization},
            )
            await connection.execute(
                text(
                    """INSERT INTO plan_contract_overrides (id,organization_id,contract_id,entitlement_key,value_kind,integer_value,state,justification,requested_by_user_id,approved_by_user_id,starts_at,ends_at)
                       VALUES (:id,:organization,:contract,'seats.active_members.max','limit',1,'active','P52-05',:admin,:approver,:starts,:ends)"""
                ),
                {
                    "id": uuid4(),
                    "organization": organization,
                    "contract": contract,
                    "admin": admin,
                    "approver": approver,
                    "starts": now - timedelta(minutes=1),
                    "ends": now + timedelta(hours=1),
                },
            )
            token_hash = await connection.scalar(
                text("SELECT token_hash FROM user_invitations WHERE id=:invitation"), {"invitation": invitation_id}
            )
        async with app.invitation_acceptance_unit_of_work(InvitationAcceptanceContext(request_id=str(uuid4()))) as unit:
            result = await unit.session.scalar(
                text(
                    "SELECT app_private.accept_invitation_new_account_audited(:token,:user,:membership,'Accept','hash',:now)"
                ),
                {"token": token_hash, "user": uuid4(), "membership": uuid4(), "now": now},
            )
            await unit.commit()
        assert result["code"] == "seat_limit_reached"
        assert invitation_id is not None
        async with app.tenant_unit_of_work(TenantContext(admin, organization, str(uuid4()))) as unit:
            last_admin = await unit.session.scalar(
                text("SELECT app_private.tenant_update_membership_audited(:membership,NULL,'disabled',1,:now)"),
                {
                    "membership": (
                        await unit.session.scalar(
                            text("SELECT id FROM memberships WHERE organization_id=:organization"),
                            {"organization": organization},
                        )
                    ),
                    "now": now,
                },
            )
            await unit.commit()
        assert last_admin["code"] == "last_active_administrator"
    finally:
        if (
            organization is not None
            and admin is not None
            and approver is not None
            and plan is not None
            and version is not None
        ):
            await _cleanup(owner, organization, admin, approver, plan, version)
        await app.close()
        await owner.close()
