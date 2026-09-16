from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.app.application.audit_events import platform_audit_event
from backend.app.application.errors import ProvisioningServiceUnavailable
from backend.app.application.tenancy import ActorContext, TenantContext
from backend.app.application.use_cases.organization import UpdateMembershipUseCase
from backend.app.domain.audit import (
    AuditAction,
    AuditActorKind,
    AuditEventDraft,
    AuditEventFilter,
    AuditScope,
    AuditSource,
)
from backend.app.domain.identity import MembershipRole, MembershipStatus
from backend.app.domain.organization import UpdateMembershipCommand
from backend.app.domain.provisioning import InvitationDeliveryStatus
from backend.app.infrastructure.clock import SystemClock
from backend.app.infrastructure.postgres import PostgresDatabase, SqlAlchemyAuditRecorder
from backend.app.infrastructure.postgres.organization_gateway import SqlAlchemyOrganizationAdministrationGateway

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class AuditFixture:
    organization_a: UUID
    organization_b: UUID
    admin_a: UUID
    sales_a: UUID
    admin_b: UUID
    platform_admin: UUID
    membership_admin_a: UUID
    membership_sales_a: UUID
    membership_admin_b: UUID


def _urls() -> tuple[str, str]:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not app_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("PostgreSQL réel est requis pour l’audit append-only.")
    return app_url, owner_url


def _database(url: str, pool_size: int = 2) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=2,
        pool_size=pool_size,
        max_overflow=0,
        pool_timeout_seconds=3,
        statement_timeout_ms=5_000,
    )


async def _create_fixture(owner: PostgresDatabase) -> AuditFixture:
    fixture = AuditFixture(*(uuid4() for _ in range(9)))
    parameters = asdict(fixture)
    now = datetime.now(UTC).replace(microsecond=0)
    async with owner.engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, email_normalized, display_name, password_hash, status,
                    platform_role, created_at, updated_at, version
                ) VALUES
                    (:admin_a, :email_admin_a, :email_admin_a, 'Admin A', 'hash', 'active', NULL, :now, :now, 1),
                    (:sales_a, :email_sales_a, :email_sales_a, 'Ventes A', 'hash', 'active', NULL, :now, :now, 1),
                    (:admin_b, :email_admin_b, :email_admin_b, 'Admin B', 'hash', 'active', NULL, :now, :now, 1),
                    (:platform_admin, :email_platform, :email_platform, 'Plateforme', 'hash', 'active',
                     'platform_admin', :now, :now, 1)
                """
            ),
            {
                **parameters,
                "email_admin_a": f"audit-admin-a-{fixture.admin_a}@example.ca",
                "email_sales_a": f"audit-sales-a-{fixture.sales_a}@example.ca",
                "email_admin_b": f"audit-admin-b-{fixture.admin_b}@example.ca",
                "email_platform": f"audit-platform-{fixture.platform_admin}@example.ca",
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO organizations (
                    id, name, locale, timezone, status, created_by, activated_at,
                    created_at, updated_at, version
                ) VALUES
                    (:organization_a, 'Audit A', 'fr-CA', 'America/Toronto', 'active',
                     :platform_admin, :now, :now, :now, 1),
                    (:organization_b, 'Audit B', 'fr-CA', 'America/Toronto', 'active',
                     :platform_admin, :now, :now, :now, 1)
                """
            ),
            {**parameters, "now": now},
        )
        await connection.execute(
            text(
                """
                INSERT INTO memberships (
                    id, organization_id, user_id, role, status, created_by, updated_by,
                    created_at, updated_at, version
                ) VALUES
                    (:membership_admin_a, :organization_a, :admin_a, 'admin', 'active',
                     :platform_admin, :platform_admin, :now, :now, 1),
                    (:membership_sales_a, :organization_a, :sales_a, 'sales', 'active',
                     :platform_admin, :platform_admin, :now, :now, 1),
                    (:membership_admin_b, :organization_b, :admin_b, 'manager', 'active',
                     :platform_admin, :platform_admin, :now, :now, 1)
                """
            ),
            {**parameters, "now": now},
        )
    return fixture


async def _cleanup(owner: PostgresDatabase, fixture: AuditFixture) -> None:
    parameters = asdict(fixture)
    async with owner.engine.begin() as connection:
        await connection.execute(
            text(
                """DELETE FROM audit_events
                   WHERE organization_id IN (:organization_a, :organization_b)
                      OR actor_id IN (:admin_a, :sales_a, :admin_b, :platform_admin)"""
            ),
            parameters,
        )
        await connection.execute(
            text(
                "DELETE FROM invitation_delivery_attempts WHERE organization_id IN (:organization_a, :organization_b)"
            ),
            parameters,
        )
        await connection.execute(
            text("DELETE FROM user_invitations WHERE organization_id IN (:organization_a, :organization_b)"),
            parameters,
        )
        await connection.execute(
            text("DELETE FROM organizations WHERE id IN (:organization_a, :organization_b)"),
            parameters,
        )
        await connection.execute(
            text("DELETE FROM users WHERE id IN (:admin_a, :sales_a, :admin_b, :platform_admin)"),
            parameters,
        )


def _tenant_event(fixture: AuditFixture, *, organization_id: UUID, actor_id: UUID, request_id: str) -> AuditEventDraft:
    entity_id = fixture.membership_sales_a if organization_id == fixture.organization_a else fixture.membership_admin_b
    return AuditEventDraft(
        id=uuid4(),
        scope=AuditScope.TENANT,
        action=AuditAction.MEMBERSHIP_ROLE_CHANGED,
        entity_type="membership",
        entity_id=entity_id,
        actor_kind=AuditActorKind.USER,
        actor_id=actor_id,
        organization_id=organization_id,
        request_id=request_id,
        correlation_id=request_id,
        source=AuditSource.API,
        metadata={"previous_role": "sales", "new_role": "manager"},
    )


async def _record_tenant(app: PostgresDatabase, context: TenantContext, event: AuditEventDraft) -> None:
    async with app.tenant_unit_of_work(context) as unit_of_work:
        recorder = SqlAlchemyAuditRecorder(unit_of_work.session)
        assert await recorder.record(event) == event.id
        await unit_of_work.commit()


async def _visible_ids(
    app: PostgresDatabase,
    *,
    actor_id: UUID,
    audit_scope: str,
    organization_id: UUID | None = None,
) -> set[UUID]:
    async with app.unit_of_work() as unit_of_work:
        await unit_of_work.session.execute(
            text(
                """
                SELECT set_config('app.actor_id', :actor_id, true),
                       set_config('app.organization_id', :organization_id, true),
                       set_config('app.audit_scope', :audit_scope, true),
                       set_config('app.request_id', 'audit-read', true)
                """
            ),
            {
                "actor_id": str(actor_id),
                "organization_id": str(organization_id) if organization_id else "",
                "audit_scope": audit_scope,
            },
        )
        return set((await unit_of_work.session.scalars(text("SELECT id FROM audit_events"))).all())


async def test_append_is_atomic_and_a_failed_audit_rolls_back_business_state() -> None:
    app_url, owner_url = _urls()
    app = _database(app_url)
    owner = _database(owner_url, 1)
    fixture = await _create_fixture(owner)
    request_id = "audit-atomic-success"
    committed = _tenant_event(
        fixture,
        organization_id=fixture.organization_a,
        actor_id=fixture.admin_a,
        request_id=request_id,
    )
    rolled_back = _tenant_event(
        fixture,
        organization_id=fixture.organization_a,
        actor_id=fixture.admin_a,
        request_id="different-request",
    )
    try:
        await _record_tenant(
            app,
            TenantContext(fixture.admin_a, fixture.organization_a, request_id),
            committed,
        )

        with pytest.raises(DBAPIError):
            async with app.tenant_unit_of_work(
                TenantContext(fixture.admin_a, fixture.organization_a, "audit-atomic-failure")
            ) as unit_of_work:
                await unit_of_work.session.execute(
                    text("UPDATE organizations SET name = 'Ne doit pas persister' WHERE id = :id"),
                    {"id": fixture.organization_a},
                )
                await SqlAlchemyAuditRecorder(unit_of_work.session).record(rolled_back)

        async with owner.engine.connect() as connection:
            organization_name = await connection.scalar(
                text("SELECT name FROM organizations WHERE id = :id"), {"id": fixture.organization_a}
            )
            event_ids = set(
                (
                    await connection.scalars(
                        text("SELECT id FROM audit_events WHERE id IN (:committed, :rolled_back)"),
                        {"committed": committed.id, "rolled_back": rolled_back.id},
                    )
                ).all()
            )
    finally:
        await _cleanup(owner, fixture)
        await app.close()
        await owner.close()

    assert organization_name == "Audit A"
    assert event_ids == {committed.id}


async def test_rls_separates_tenants_sales_and_platform_scope() -> None:
    app_url, owner_url = _urls()
    app = _database(app_url)
    owner = _database(owner_url, 1)
    fixture = await _create_fixture(owner)
    event_a = _tenant_event(
        fixture,
        organization_id=fixture.organization_a,
        actor_id=fixture.admin_a,
        request_id="audit-tenant-a",
    )
    event_b = _tenant_event(
        fixture,
        organization_id=fixture.organization_b,
        actor_id=fixture.admin_b,
        request_id="audit-tenant-b",
    )
    platform_event = AuditEventDraft(
        id=uuid4(),
        scope=AuditScope.PLATFORM,
        action=AuditAction.ORGANIZATION_PROVISIONED,
        entity_type="organization",
        entity_id=fixture.organization_a,
        actor_kind=AuditActorKind.USER,
        actor_id=fixture.platform_admin,
        organization_id=fixture.organization_a,
        request_id="audit-platform",
        correlation_id="audit-platform",
        source=AuditSource.API,
    )
    try:
        await _record_tenant(
            app,
            TenantContext(fixture.admin_a, fixture.organization_a, event_a.request_id),
            event_a,
        )
        await _record_tenant(
            app,
            TenantContext(fixture.admin_b, fixture.organization_b, event_b.request_id),
            event_b,
        )
        async with app.actor_unit_of_work(
            ActorContext(fixture.platform_admin, platform_event.request_id)
        ) as unit_of_work:
            await SqlAlchemyAuditRecorder(unit_of_work.session).record(platform_event)
            await unit_of_work.commit()

        tenant_a_ids = await _visible_ids(
            app,
            actor_id=fixture.admin_a,
            organization_id=fixture.organization_a,
            audit_scope="tenant",
        )
        tenant_b_ids = await _visible_ids(
            app,
            actor_id=fixture.admin_b,
            organization_id=fixture.organization_b,
            audit_scope="tenant",
        )
        sales_ids = await _visible_ids(
            app,
            actor_id=fixture.sales_a,
            organization_id=fixture.organization_a,
            audit_scope="tenant",
        )
        platform_ids = await _visible_ids(
            app,
            actor_id=fixture.platform_admin,
            audit_scope="platform",
        )
        wrong_scope_ids = await _visible_ids(
            app,
            actor_id=fixture.platform_admin,
            audit_scope="tenant",
        )
    finally:
        await _cleanup(owner, fixture)
        await app.close()
        await owner.close()

    assert tenant_a_ids == {event_a.id}
    assert tenant_b_ids == {event_b.id}
    assert sales_ids == set()
    assert platform_event.id in platform_ids
    assert event_a.id not in platform_ids
    assert event_b.id not in platform_ids
    assert wrong_scope_ids == set()


async def test_audit_reader_applies_rls_filters_order_and_actor_projection() -> None:
    app_url, owner_url = _urls()
    app = _database(app_url)
    owner = _database(owner_url, 1)
    fixture = await _create_fixture(owner)
    event_a = _tenant_event(
        fixture,
        organization_id=fixture.organization_a,
        actor_id=fixture.admin_a,
        request_id="audit-reader-a",
    )
    event_b = _tenant_event(
        fixture,
        organization_id=fixture.organization_b,
        actor_id=fixture.admin_b,
        request_id="audit-reader-b",
    )
    filters = AuditEventFilter(
        occurred_from=datetime.now(UTC) - timedelta(days=1),
        occurred_to=datetime.now(UTC) + timedelta(days=1),
        action=AuditAction.MEMBERSHIP_ROLE_CHANGED,
        entity_type="membership",
        actor_id=fixture.admin_a,
    )
    try:
        await _record_tenant(app, TenantContext(fixture.admin_a, fixture.organization_a, event_a.request_id), event_a)
        await _record_tenant(app, TenantContext(fixture.admin_b, fixture.organization_b, event_b.request_id), event_b)

        async with app.tenant_audit_read_unit_of_work(
            TenantContext(fixture.admin_a, fixture.organization_a, "audit-reader-list")
        ) as unit_of_work:
            rows = await unit_of_work.reader.list_events(
                filters=filters,
                before_occurred_at=None,
                before_id=None,
                limit=51,
            )
        async with app.tenant_audit_read_unit_of_work(
            TenantContext(fixture.sales_a, fixture.organization_a, "audit-reader-sales")
        ) as unit_of_work:
            sales_rows = await unit_of_work.reader.list_events(
                filters=filters,
                before_occurred_at=None,
                before_id=None,
                limit=51,
            )
    finally:
        await _cleanup(owner, fixture)
        await app.close()
        await owner.close()

    assert [row.id for row in rows] == [event_a.id]
    assert rows[0].actor.display_name == "Admin A"
    assert rows[0].metadata == {"previous_role": "sales", "new_role": "manager"}
    assert sales_rows == ()


async def test_database_privileges_make_audit_strictly_append_only() -> None:
    app_url, owner_url = _urls()
    app = _database(app_url)
    owner = _database(owner_url, 1)
    fixture = await _create_fixture(owner)
    try:
        async with app.engine.connect() as connection:
            privileges = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT
                            has_table_privilege(current_user, 'public.audit_events', 'SELECT') AS can_select,
                            has_table_privilege(current_user, 'public.audit_events', 'INSERT') AS can_insert,
                            has_table_privilege(current_user, 'public.audit_events', 'UPDATE') AS can_update,
                            has_table_privilege(current_user, 'public.audit_events', 'DELETE') AS can_delete,
                            has_table_privilege(current_user, 'public.audit_events', 'TRUNCATE') AS can_truncate
                        """
                        )
                    )
                )
                .mappings()
                .one()
            )
            metadata = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT relation.relrowsecurity, relation.relforcerowsecurity,
                               pg_catalog.pg_get_userbyid(procedure.proowner) AS function_owner,
                               procedure.prosecdef, procedure.proconfig,
                               has_function_privilege(
                                   current_user,
                                   'app_private.append_audit_event(uuid,text,uuid,text,uuid,text,text,uuid,text,text,text,jsonb,smallint)',
                                   'EXECUTE'
                               ) AS can_execute
                        FROM pg_catalog.pg_class AS relation
                        CROSS JOIN pg_catalog.pg_proc AS procedure
                        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
                        WHERE relation.oid = 'public.audit_events'::regclass
                          AND namespace.nspname = 'app_private'
                          AND procedure.proname = 'append_audit_event'
                        """
                        )
                    )
                )
                .mappings()
                .one()
            )
            policies = set(
                (
                    await connection.scalars(
                        text("SELECT policyname FROM pg_policies WHERE tablename = 'audit_events'")
                    )
                ).all()
            )
            public_execute = await connection.scalar(
                text(
                    """
                    SELECT count(*) FROM information_schema.routine_privileges
                    WHERE routine_schema = 'app_private' AND routine_name = 'append_audit_event'
                      AND grantee = 'PUBLIC'
                    """
                )
            )

        for statement in (
            "INSERT INTO audit_events (id) VALUES (gen_random_uuid())",
            "UPDATE audit_events SET action = action",
            "DELETE FROM audit_events",
            "TRUNCATE audit_events",
        ):
            with pytest.raises(DBAPIError):
                async with app.unit_of_work() as unit_of_work:
                    await unit_of_work.session.execute(text(statement))
    finally:
        await _cleanup(owner, fixture)
        await app.close()
        await owner.close()

    assert dict(privileges) == {
        "can_select": True,
        "can_insert": False,
        "can_update": False,
        "can_delete": False,
        "can_truncate": False,
    }
    assert metadata["relrowsecurity"] is True
    assert metadata["relforcerowsecurity"] is True
    assert metadata["function_owner"] == "prospect_rls_definer"
    assert metadata["prosecdef"] is True
    assert "search_path=pg_catalog, public, pg_temp" in metadata["proconfig"]
    assert metadata["can_execute"] is True
    assert policies == {"audit_events_platform_read", "audit_events_tenant_read"}
    assert public_execute == 0


class _Sessions:
    async def revoke_user_before_version(self, user_id: UUID, minimum_valid_version: int) -> None:
        del user_id, minimum_valid_version


async def test_membership_mutation_and_two_audit_events_commit_atomically() -> None:
    app_url, owner_url = _urls()
    app = _database(app_url)
    owner = _database(owner_url, 1)
    fixture = await _create_fixture(owner)
    request_id = "audit-membership-use-case"
    try:
        use_case = UpdateMembershipUseCase(
            SqlAlchemyOrganizationAdministrationGateway(app),
            _Sessions(),  # type: ignore[arg-type]
            SystemClock(),
            app.tenant_audited_unit_of_work,
        )
        await use_case.execute(
            context=TenantContext(fixture.admin_a, fixture.organization_a, request_id),
            membership_id=fixture.membership_sales_a,
            command=UpdateMembershipCommand(
                version=1,
                role=MembershipRole.MANAGER,
                status=MembershipStatus.DISABLED,
            ),
            has_capability=True,
        )
        async with owner.engine.connect() as connection:
            membership = (
                (
                    await connection.execute(
                        text("SELECT role, status FROM memberships WHERE id=:id"),
                        {"id": fixture.membership_sales_a},
                    )
                )
                .mappings()
                .one()
            )
            events = (
                (
                    await connection.execute(
                        text(
                            """SELECT action, request_id, correlation_id FROM audit_events
                           WHERE entity_id=:id ORDER BY occurred_at, id"""
                        ),
                        {"id": fixture.membership_sales_a},
                    )
                )
                .mappings()
                .all()
            )
    finally:
        await _cleanup(owner, fixture)
        await app.close()
        await owner.close()

    assert dict(membership) == {"role": "manager", "status": "disabled"}
    assert [event["action"] for event in events] == [
        "membership.role_changed",
        "membership.status_changed",
    ]
    assert all(event["request_id"] == request_id for event in events)
    assert all(event["correlation_id"] == request_id for event in events)


async def test_delivery_finalization_is_audited_once_and_rejects_a_divergent_replay() -> None:
    app_url, owner_url = _urls()
    app = _database(app_url)
    owner = _database(owner_url, 1)
    fixture = await _create_fixture(owner)
    invitation_id = uuid4()
    attempt_id = uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    context = ActorContext(fixture.platform_admin, "audit-delivery-finalization")
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    """INSERT INTO user_invitations (
                           id,organization_id,email,email_normalized,role,invitation_kind,token_hash,
                           expires_at,invited_by,delivery_status,created_at,updated_at)
                       VALUES (:id,:organization_id,'delivery@example.ca','delivery@example.ca','admin',
                           'initial_administrator',:token_hash,:expires_at,:actor,'pending',:now,:now)"""
                ),
                {
                    "id": invitation_id,
                    "organization_id": fixture.organization_a,
                    "token_hash": uuid4().hex + uuid4().hex,
                    "expires_at": now.replace(year=now.year + 1),
                    "actor": fixture.platform_admin,
                    "now": now,
                },
            )
            await connection.execute(
                text(
                    """INSERT INTO invitation_delivery_attempts (
                           id,organization_id,invitation_id,request_id,kind,status,requested_by,created_at)
                       VALUES (:id,:organization_id,:invitation_id,:request_id,'initial','pending',:actor,:now)"""
                ),
                {
                    "id": attempt_id,
                    "organization_id": fixture.organization_a,
                    "invitation_id": invitation_id,
                    "request_id": uuid4(),
                    "actor": fixture.platform_admin,
                    "now": now,
                },
            )

        async with app.platform_audited_unit_of_work(context) as unit_of_work:
            finalized = await unit_of_work.mutations.finalize_delivery(
                invitation_id=invitation_id,
                delivery_attempt_id=attempt_id,
                sent=True,
                failure_code=None,
                now=now,
            )
            assert finalized.transitioned is True
            await unit_of_work.audit.record(
                platform_audit_event(
                    context,
                    AuditAction.INITIAL_INVITATION_DELIVERY_COMPLETED,
                    invitation_id,
                    {
                        "delivery_status": InvitationDeliveryStatus.SENT.value,
                        "delivery_kind": "initial",
                        "delivery_attempt_id": attempt_id,
                    },
                )
            )
            await unit_of_work.commit()

        async with app.platform_audited_unit_of_work(context) as unit_of_work:
            replayed = await unit_of_work.mutations.finalize_delivery(
                invitation_id=invitation_id,
                delivery_attempt_id=attempt_id,
                sent=True,
                failure_code=None,
                now=now,
            )
            assert replayed.transitioned is False
            await unit_of_work.commit()

        with pytest.raises(ProvisioningServiceUnavailable):
            async with app.platform_audited_unit_of_work(context) as unit_of_work:
                await unit_of_work.mutations.finalize_delivery(
                    invitation_id=invitation_id,
                    delivery_attempt_id=attempt_id,
                    sent=False,
                    failure_code="delivery_failed",
                    now=now,
                )
                await unit_of_work.commit()

        async with owner.engine.connect() as connection:
            event_count = await connection.scalar(
                text("SELECT count(*) FROM audit_events WHERE entity_id=:id AND action=:action"),
                {"id": invitation_id, "action": AuditAction.INITIAL_INVITATION_DELIVERY_COMPLETED.value},
            )
    finally:
        await _cleanup(owner, fixture)
        await app.close()
        await owner.close()

    assert event_count == 1
