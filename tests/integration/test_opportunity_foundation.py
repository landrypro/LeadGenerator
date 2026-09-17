import os
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.app.application.errors import OrganizationAdministrationUnavailable
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases.opportunities import TransitionOpportunityUseCase
from backend.app.domain.opportunity import (
    OpportunityDraft,
    OpportunityEventType,
    OpportunityEventView,
    OpportunityStageCode,
    OpportunityView,
)
from backend.app.domain.prospect import ProspectDraft, ProspectOrigin, ProspectView
from backend.app.infrastructure.postgres import PostgresDatabase

pytestmark = pytest.mark.integration


class _FixedClock:
    def __init__(self, value: datetime) -> None:
        self._value = value

    def now(self) -> datetime:
        return self._value


@dataclass(frozen=True, slots=True)
class OpportunityFixture:
    organization_a_id: UUID
    organization_b_id: UUID
    actor_a_id: UUID
    actor_b_id: UUID
    membership_a_id: UUID
    membership_b_id: UUID


def database_urls() -> tuple[str, str]:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not app_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("Les URL PostgreSQL applicative et proprietaire sont requises.")
    return app_url, owner_url


def create_database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=2,
        pool_size=1,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=2_000,
    )


def context_for_a(fixture: OpportunityFixture, *, request_id: str) -> TenantContext:
    return TenantContext(
        actor_id=fixture.actor_a_id,
        organization_id=fixture.organization_a_id,
        request_id=request_id,
    )


def context_for_b(fixture: OpportunityFixture, *, request_id: str) -> TenantContext:
    return TenantContext(
        actor_id=fixture.actor_b_id,
        organization_id=fixture.organization_b_id,
        request_id=request_id,
    )


async def create_fixture(owner: PostgresDatabase) -> OpportunityFixture:
    fixture = OpportunityFixture(
        organization_a_id=uuid4(),
        organization_b_id=uuid4(),
        actor_a_id=uuid4(),
        actor_b_id=uuid4(),
        membership_a_id=uuid4(),
        membership_b_id=uuid4(),
    )
    values = asdict(fixture)
    now = datetime.now(UTC).replace(microsecond=0)
    async with owner.engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, email_normalized, display_name, password_hash, status,
                    last_active_organization_id, created_at, updated_at
                ) VALUES
                    (:actor_a_id, :email_a, :email_a, 'Acteur opportunité A', 'hash-a', 'active', NULL, :now, :now),
                    (:actor_b_id, :email_b, :email_b, 'Acteur opportunité B', 'hash-b', 'active', NULL, :now, :now)
                """
            ),
            {
                **values,
                "email_a": f"opportunity-a-{fixture.actor_a_id}@example.ca",
                "email_b": f"opportunity-b-{fixture.actor_b_id}@example.ca",
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO organizations (
                    id, name, timezone, status, created_by, activated_at, created_at, updated_at
                ) VALUES
                    (:organization_a_id, 'Organisation opportunité A', 'America/Toronto', 'active', :actor_a_id, :now, :now, :now),
                    (:organization_b_id, 'Organisation opportunité B', 'America/Toronto', 'active', :actor_b_id, :now, :now, :now)
                """
            ),
            {**values, "now": now},
        )
        await connection.execute(
            text(
                """
                INSERT INTO memberships (
                    id, organization_id, user_id, role, created_by, updated_by, created_at, updated_at, version
                ) VALUES
                    (:membership_a_id, :organization_a_id, :actor_a_id, 'admin', :actor_a_id, :actor_a_id, :now, :now, 1),
                    (:membership_b_id, :organization_b_id, :actor_b_id, 'admin', :actor_b_id, :actor_b_id, :now, :now, 1)
                """
            ),
            {**values, "now": now},
        )
    return fixture


async def delete_fixture(owner: PostgresDatabase, fixture: OpportunityFixture) -> None:
    values = asdict(fixture)
    async with owner.engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM audit_events WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            values,
        )
        await connection.execute(
            text("DELETE FROM organizations WHERE id IN (:organization_a_id, :organization_b_id)"), values
        )
        await connection.execute(text("DELETE FROM users WHERE id IN (:actor_a_id, :actor_b_id)"), values)


async def create_opportunity(
    app: PostgresDatabase,
    fixture: OpportunityFixture,
    *,
    is_a: bool,
    now: datetime,
) -> tuple[ProspectView, OpportunityView]:
    context = (
        context_for_a(fixture, request_id=f"opportunity-seed-a-{uuid4()}")
        if is_a
        else context_for_b(fixture, request_id=f"opportunity-seed-b-{uuid4()}")
    )
    organization_id = fixture.organization_a_id if is_a else fixture.organization_b_id
    actor_id = fixture.actor_a_id if is_a else fixture.actor_b_id
    membership_id = fixture.membership_a_id if is_a else fixture.membership_b_id
    async with app.tenant_prospect_unit_of_work(context) as unit_of_work:
        prospect = await unit_of_work.prospects.add(
            ProspectDraft(
                organization_id=organization_id,
                internal_alias=f"Prospect opportunité {'A' if is_a else 'B'}",
                origin=ProspectOrigin.MANUAL,
                source_label="Recette opportunité",
            ),
            now=now,
        )
        opportunity = await unit_of_work.opportunities.add(
            OpportunityDraft(
                prospect_id=prospect.id,
                owner_membership_id=membership_id,
                name="Opportunité de test",
                amount=Decimal("1250.2500"),
                currency_code="CAD",
                probability=10,
                expected_close_on=now.date(),
                idempotency_key=str(uuid4()),
            ),
            organization_id=organization_id,
            actor_id=actor_id,
            now=now,
        )
        await unit_of_work.commit()
    return prospect, opportunity


async def test_opportunity_tables_are_rls_protected_and_privileges_are_minimal() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    try:
        async with owner.engine.connect() as connection:
            rls_rows = (
                (
                    await connection.execute(
                        text(
                            """
                            SELECT relname, relrowsecurity, relforcerowsecurity
                            FROM pg_class
                            WHERE relname IN ('opportunities', 'opportunity_events')
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
                            SELECT policyname
                            FROM pg_policies
                            WHERE schemaname = 'public'
                              AND tablename IN ('opportunities', 'opportunity_events')
                            """
                        )
                    )
                ).all()
            )
            public_grants = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM information_schema.table_privileges
                    WHERE table_schema = 'public'
                      AND table_name IN ('opportunities', 'opportunity_events')
                      AND grantee = 'PUBLIC'
                    """
                )
            )
        async with app.engine.connect() as connection:
            privileges = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT
                            has_table_privilege(current_user, 'public.opportunities', 'DELETE') AS opportunity_delete,
                            has_table_privilege(current_user, 'public.opportunity_events', 'UPDATE') AS event_update,
                            has_table_privilege(current_user, 'public.opportunity_events', 'DELETE') AS event_delete
                        """
                        )
                    )
                )
                .mappings()
                .one()
            )
    finally:
        await app.close()
        await owner.close()

    assert len(rls_rows) == 2
    assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rls_rows)
    assert policies == {"opportunities_tenant_isolation", "opportunity_events_tenant_isolation"}
    assert public_grants == 0
    assert not any(privileges.values())


async def test_opportunity_repository_enforces_tenant_visibility_and_optimistic_updates() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_fixture(owner)
    now = datetime.now(UTC).replace(microsecond=0)
    try:
        prospect_a, opportunity_a = await create_opportunity(app, fixture, is_a=True, now=now)
        _prospect_b, opportunity_b = await create_opportunity(app, fixture, is_a=False, now=now)

        async with app.tenant_prospect_unit_of_work(
            context_for_a(fixture, request_id=f"opportunity-read-a-{uuid4()}")
        ) as uow:
            loaded = await uow.opportunities.get_for_update(opportunity_a.id)
            invisible = await uow.opportunities.get(opportunity_b.id)
            listed = await uow.opportunities.list_for_prospect(prospect_a.id, limit=10)
            updated = await uow.opportunities.update(
                opportunity_a.id,
                expected_version=opportunity_a.version,
                changes={"name": "Opportunité renommée"},
                now=now,
            )
            owner_is_active = await uow.opportunities.is_active_owner(fixture.membership_a_id)
            await uow.commit()

        async with app.tenant_prospect_unit_of_work(
            context_for_b(fixture, request_id=f"opportunity-read-b-{uuid4()}")
        ) as uow:
            invisible_from_b = await uow.opportunities.get(opportunity_a.id)
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert loaded is not None
    assert loaded.owner_membership_is_active is True
    assert invisible is None
    assert tuple(item.id for item in listed) == (opportunity_a.id,)
    assert updated is not None
    assert updated.name == "Opportunité renommée"
    assert updated.version == opportunity_a.version + 1
    assert owner_is_active is True
    assert invisible_from_b is None


async def test_opportunity_can_be_won_from_proposal_atomically() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_fixture(owner)
    now = datetime.now(UTC).replace(microsecond=0)
    context = context_for_a(fixture, request_id=f"opportunity-win-{uuid4()}")
    try:
        prospect, opportunity = await create_opportunity(app, fixture, is_a=True, now=now)
        async with app.tenant_prospect_unit_of_work(context) as uow:
            proposal = await uow.opportunities.update(
                opportunity.id,
                expected_version=opportunity.version,
                changes={"stage_code": OpportunityStageCode.PROPOSAL},
                now=now,
            )
            await uow.commit()
        assert proposal is not None

        use_case = TransitionOpportunityUseCase(app.tenant_prospect_unit_of_work, _FixedClock(now))
        won = await use_case.execute(
            context=context,
            opportunity_id=proposal.id,
            expected_version=proposal.version,
            to_stage=OpportunityStageCode.WON,
            reason_code=None,
            reason_note=None,
            idempotency_key=str(uuid4()),
            can_close=True,
            can_manage=True,
            current_membership_id=fixture.membership_a_id,
        )

        async with app.tenant_prospect_unit_of_work(context) as uow:
            persisted = await uow.opportunities.get(won.id)
            events = await uow.opportunity_events.list_for_opportunity(won.id, limit=10)
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert persisted is not None
    assert persisted.prospect_id == prospect.id
    assert persisted.stage_code is OpportunityStageCode.WON
    assert persisted.probability == 100
    assert persisted.closed_at == now
    assert persisted.loss_reason_code is None
    assert persisted.loss_reason_note is None
    assert persisted.version == proposal.version + 1
    assert len(events) == 1
    assert events[0].from_stage is OpportunityStageCode.PROPOSAL
    assert events[0].to_stage is OpportunityStageCode.WON


async def test_opportunity_sql_constraints_and_composite_references_are_enforced() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_fixture(owner)
    now = datetime.now(UTC).replace(microsecond=0)
    try:
        prospect_a, opportunity_a = await create_opportunity(app, fixture, is_a=True, now=now)
        prospect_b, opportunity_b = await create_opportunity(app, fixture, is_a=False, now=now)
        context_a = context_for_a(fixture, request_id=f"opportunity-constraints-a-{uuid4()}")

        for amount, currency_code, stage_code, probability, loss_reason_code in (
            ("NaN", "CAD", "discovery", 10, None),
            ("1.0000", "cad", "discovery", 10, None),
            ("1.0000", "CAD", "lost", 0, "other"),
        ):
            with pytest.raises(DBAPIError):
                async with app.tenant_unit_of_work(context_a) as uow:
                    await uow.session.execute(
                        text(
                            """
                            INSERT INTO public.opportunities (
                                id, organization_id, prospect_id, owner_membership_id, name, amount, currency_code,
                                probability, stage_code, expected_close_on, loss_reason_code, created_by, closed_at
                            ) VALUES (
                                :id, :organization_id, :prospect_id, :owner_membership_id, 'Opportunité invalide',
                                CAST(:amount AS numeric), :currency_code, :probability, :stage_code, :expected_close_on,
                                :loss_reason_code, :created_by,
                                CASE WHEN :stage_code = 'lost' THEN :now ELSE NULL END
                            )
                            """
                        ),
                        {
                            "id": uuid4(),
                            "organization_id": fixture.organization_a_id,
                            "prospect_id": prospect_a.id,
                            "owner_membership_id": fixture.membership_a_id,
                            "amount": amount,
                            "currency_code": currency_code,
                            "probability": probability,
                            "stage_code": stage_code,
                            "expected_close_on": now.date(),
                            "loss_reason_code": loss_reason_code,
                            "created_by": fixture.actor_a_id,
                            "now": now,
                        },
                    )

        with pytest.raises(DBAPIError):
            async with app.tenant_unit_of_work(context_a) as uow:
                await uow.session.execute(
                    text(
                        """
                        INSERT INTO public.opportunity_events (
                            id, organization_id, prospect_id, opportunity_id, actor_id, event_type,
                            from_stage, to_stage, from_version, resulting_version, changed_fields,
                            idempotency_key, command_fingerprint, occurred_at
                        ) VALUES (
                            :id, :organization_id, :prospect_id, :opportunity_id, :actor_id, 'created',
                            NULL, 'discovery', 1, 1, '{}'::jsonb, :idempotency_key, :command_fingerprint, :now
                        )
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": fixture.organization_a_id,
                        "prospect_id": prospect_a.id,
                        "opportunity_id": opportunity_b.id,
                        "actor_id": fixture.actor_a_id,
                        "idempotency_key": str(uuid4()),
                        "command_fingerprint": "f" * 64,
                        "now": now,
                    },
                )

        event = OpportunityEventView(
            id=uuid4(),
            organization_id=fixture.organization_a_id,
            prospect_id=prospect_a.id,
            opportunity_id=opportunity_a.id,
            actor_id=fixture.actor_a_id,
            event_type=OpportunityEventType.CREATED,
            from_stage=None,
            to_stage=OpportunityStageCode.DISCOVERY,
            from_version=1,
            resulting_version=1,
            changed_fields={},
            reason_code=None,
            reason_note=None,
            idempotency_key=str(uuid4()),
            command_fingerprint="a" * 64,
            occurred_at=now,
        )
        async with app.tenant_prospect_unit_of_work(context_a) as uow:
            inserted_event = await uow.opportunity_events.add(event)
            replay = await uow.opportunity_events.get_by_idempotency_key(
                event_type=OpportunityEventType.CREATED,
                idempotency_key=event.idempotency_key,
            )
            await uow.commit()

        with pytest.raises(OrganizationAdministrationUnavailable) as replay_error:
            async with app.tenant_prospect_unit_of_work(context_a) as uow:
                await uow.opportunity_events.add(replace(event, id=uuid4()))
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert inserted_event.id == event.id
    assert replay is not None
    assert replay.id == event.id
    assert isinstance(replay_error.value.__cause__, DBAPIError)
    assert prospect_b.id != prospect_a.id


async def test_opportunity_rls_defaults_to_deny_cross_tenant_reads_and_writes() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_fixture(owner)
    now = datetime.now(UTC).replace(microsecond=0)
    try:
        _prospect_a, opportunity_a = await create_opportunity(app, fixture, is_a=True, now=now)
        async with app.unit_of_work() as uow:
            without_context = await uow.session.scalar(text("SELECT count(*) FROM public.opportunities"))

        with pytest.raises(DBAPIError):
            async with app.tenant_unit_of_work(
                context_for_b(fixture, request_id=f"opportunity-cross-write-{uuid4()}")
            ) as uow:
                await uow.session.execute(
                    text(
                        """
                        INSERT INTO public.opportunities (
                            id, organization_id, prospect_id, owner_membership_id, name, amount, currency_code,
                            probability, stage_code, expected_close_on, created_by
                        ) VALUES (
                            :id, :organization_id, :prospect_id, :owner_membership_id, 'Fuite', 1.0000, 'CAD',
                            10, 'discovery', :expected_close_on, :created_by
                        )
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": fixture.organization_a_id,
                        "prospect_id": uuid4(),
                        "owner_membership_id": fixture.membership_a_id,
                        "expected_close_on": date.today(),
                        "created_by": fixture.actor_b_id,
                    },
                )
        async with app.tenant_prospect_unit_of_work(
            context_for_b(fixture, request_id=f"opportunity-cross-read-{uuid4()}")
        ) as uow:
            hidden = await uow.opportunities.get(opportunity_a.id)
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert without_context == 0
    assert hidden is None
