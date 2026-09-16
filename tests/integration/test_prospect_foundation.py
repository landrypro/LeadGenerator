import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.app.application.errors import OrganizationAdministrationUnavailable
from backend.app.application.tenancy import TenantContext
from backend.app.domain.activity import (
    ActivityDirection,
    ActivityType,
    ProspectActivityDraft,
    ProspectTaskDraft,
)
from backend.app.domain.audit import AuditAction, AuditActorKind, AuditEventDraft, AuditScope, AuditSource
from backend.app.domain.prospect import (
    ContactChannelDraft,
    ContactChannelType,
    ProspectDraft,
    ProspectOrigin,
    ProvenanceDraft,
    ProvenanceSourceKind,
)
from backend.app.infrastructure.postgres import PostgresDatabase

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class ProspectTenantFixture:
    organization_a_id: UUID
    organization_b_id: UUID
    actor_a_id: UUID
    actor_b_id: UUID


def database_urls() -> tuple[str, str]:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not app_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("Les URL PostgreSQL applicative et proprietaire sont requises.")
    return app_url, owner_url


def create_database(url: str, *, pool_size: int = 1) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=2,
        pool_size=pool_size,
        max_overflow=0,
        pool_timeout_seconds=2,
        statement_timeout_ms=2_000,
    )


async def create_fixture(owner: PostgresDatabase) -> ProspectTenantFixture:
    fixture = ProspectTenantFixture(
        organization_a_id=uuid4(),
        organization_b_id=uuid4(),
        actor_a_id=uuid4(),
        actor_b_id=uuid4(),
    )
    parameters = asdict(fixture)
    now = datetime.now(UTC).replace(microsecond=0)
    async with owner.engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, email_normalized, display_name, password_hash, status,
                    last_active_organization_id, created_at, updated_at
                )
                VALUES
                    (:actor_a_id, :email_a, :email_a, 'Acteur A', 'hash-a', 'active', NULL, :now, :now),
                    (:actor_b_id, :email_b, :email_b, 'Acteur B', 'hash-b', 'active', NULL, :now, :now)
                """
            ),
            {
                **parameters,
                "email_a": f"prospect-a-{fixture.actor_a_id}@example.ca",
                "email_b": f"prospect-b-{fixture.actor_b_id}@example.ca",
                "now": now,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO organizations (
                    id, name, timezone, status, created_by, activated_at, created_at, updated_at
                )
                VALUES
                    (:organization_a_id, 'Organisation A', 'America/Toronto', 'active', :actor_a_id, :now, :now, :now),
                    (:organization_b_id, 'Organisation B', 'America/Toronto', 'active', :actor_b_id, :now, :now, :now)
                """
            ),
            {**parameters, "now": now},
        )
        await connection.execute(
            text(
                """
                INSERT INTO memberships (
                    id, organization_id, user_id, role, created_by, updated_by, created_at, updated_at, version
                )
                VALUES
                    (:membership_a_id, :organization_a_id, :actor_a_id, 'admin', :actor_a_id, :actor_a_id, :now, :now, 1),
                    (:membership_b_id, :organization_b_id, :actor_b_id, 'admin', :actor_b_id, :actor_b_id, :now, :now, 1)
                """
            ),
            {**parameters, "membership_a_id": uuid4(), "membership_b_id": uuid4(), "now": now},
        )
    return fixture


async def delete_fixture(owner: PostgresDatabase, fixture: ProspectTenantFixture) -> None:
    async with owner.engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM audit_events WHERE organization_id IN (:organization_a_id, :organization_b_id)"),
            asdict(fixture),
        )
        await connection.execute(
            text("DELETE FROM organizations WHERE id IN (:organization_a_id, :organization_b_id)"),
            asdict(fixture),
        )
        await connection.execute(
            text("DELETE FROM users WHERE id IN (:actor_a_id, :actor_b_id)"),
            asdict(fixture),
        )


def tenant_context(fixture: ProspectTenantFixture, *, request_id: str) -> TenantContext:
    return TenantContext(
        actor_id=fixture.actor_a_id,
        organization_id=fixture.organization_a_id,
        request_id=request_id,
    )


async def test_prospect_tables_are_rls_protected_and_privileges_are_narrow() -> None:
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
                            WHERE relname IN (
                                'source_providers', 'acquisition_records', 'provenance_records',
                                'prospects', 'contacts', 'contact_channels', 'contact_permissions',
                                'prospect_activities', 'prospect_tasks', 'prospect_task_events'
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
                            SELECT policyname
                            FROM pg_policies
                            WHERE schemaname = 'public'
                              AND tablename IN (
                                  'source_providers', 'acquisition_records', 'provenance_records',
                                  'prospects', 'contacts', 'contact_channels', 'contact_permissions',
                                  'prospect_activities', 'prospect_tasks', 'prospect_task_events'
                              )
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
                      AND table_name IN (
                          'source_providers', 'acquisition_records', 'provenance_records',
                          'prospects', 'contacts', 'contact_channels', 'contact_permissions',
                          'prospect_activities', 'prospect_tasks', 'prospect_task_events'
                      )
                      AND grantee = 'PUBLIC'
                    """
                )
            )

        async with app.engine.connect() as connection:
            delete_privileges = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT
                            has_table_privilege(current_user, 'public.prospect_activities', 'DELETE') AS activities,
                            has_table_privilege(current_user, 'public.prospect_tasks', 'DELETE') AS tasks,
                            has_table_privilege(current_user, 'public.prospect_task_events', 'DELETE') AS task_events
                        """
                        )
                    )
                )
                .mappings()
                .one()
            )
        async with owner.engine.connect() as connection:
            text_limit_rows = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT table_name, column_name, character_maximum_length
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND (table_name, column_name) IN (
                              ('prospect_activities', 'summary'),
                              ('prospect_tasks', 'title')
                          )
                        """
                        )
                    )
                )
                .mappings()
                .all()
            )
            text_limits = {
                (row["table_name"], row["column_name"]): row["character_maximum_length"] for row in text_limit_rows
            }
    finally:
        await app.close()
        await owner.close()

    assert len(rls_rows) == 10
    assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rls_rows)
    assert policies == {
        "source_providers_tenant_isolation",
        "acquisition_records_tenant_isolation",
        "provenance_records_tenant_isolation",
        "prospects_tenant_isolation",
        "contacts_tenant_isolation",
        "contact_channels_tenant_isolation",
        "contact_permissions_tenant_isolation",
        "prospect_activities_tenant_isolation",
        "prospect_tasks_tenant_isolation",
        "prospect_task_events_tenant_isolation",
    }
    assert public_grants == 0
    assert not any(delete_privileges.values())
    assert text_limits == {
        ("prospect_activities", "summary"): 160,
        ("prospect_tasks", "title"): 160,
    }


async def test_prospect_repository_isolated_by_tenant_and_audited_atomically() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_fixture(owner)
    now = datetime.now(UTC).replace(microsecond=0)
    context = tenant_context(fixture, request_id=f"prospect-create-commit-{uuid4()}")
    try:
        async with app.tenant_prospect_unit_of_work(context) as unit_of_work:
            provenance = await unit_of_work.provenance.add(
                ProvenanceDraft(
                    organization_id=fixture.organization_a_id,
                    source_kind=ProvenanceSourceKind.MANUAL,
                    source_label="Appel entrant",
                    purpose="commercial_follow_up",
                    obtained_at=now,
                    attested_by=fixture.actor_a_id,
                ),
                now=now,
            )
            prospect = await unit_of_work.prospects.add(
                ProspectDraft(
                    organization_id=fixture.organization_a_id,
                    internal_alias="Entreprise QA",
                    origin=ProspectOrigin.MANUAL,
                    source_label="Saisie QA",
                ),
                now=now,
            )
            activity = await unit_of_work.activities.add(
                ProspectActivityDraft(
                    prospect_id=prospect.id,
                    activity_type=ActivityType.NOTE,
                    direction=ActivityDirection.INTERNAL,
                    summary="Note isolée",
                    occurred_at=now,
                ),
                organization_id=fixture.organization_a_id,
                actor_id=fixture.actor_a_id,
                now=now,
            )
            task = await unit_of_work.tasks.add(
                ProspectTaskDraft(
                    prospect_id=prospect.id,
                    title="Tâche isolée",
                    due_at=now.replace(year=now.year + 1),
                ),
                organization_id=fixture.organization_a_id,
                actor_id=fixture.actor_a_id,
                now=now,
            )
            channel = await unit_of_work.contact_channels.add(
                ContactChannelDraft(
                    organization_id=fixture.organization_a_id,
                    prospect_id=prospect.id,
                    channel_type=ContactChannelType.EMAIL,
                    value="qa@example.ca",
                    value_normalized="qa@example.ca",
                    provenance_id=provenance.id,
                    created_by=fixture.actor_a_id,
                ),
                now=now,
            )
            await unit_of_work.audit.record(
                AuditEventDraft(
                    id=uuid4(),
                    scope=AuditScope.TENANT,
                    action=AuditAction.PROSPECT_CREATED,
                    entity_type="prospect",
                    entity_id=prospect.id,
                    actor_kind=AuditActorKind.USER,
                    actor_id=fixture.actor_a_id,
                    organization_id=fixture.organization_a_id,
                    request_id=context.request_id,
                    correlation_id=context.request_id,
                    source=AuditSource.API,
                    metadata={"origin": "manual"},
                )
            )
            await unit_of_work.commit()

        context_b = TenantContext(
            actor_id=fixture.actor_b_id,
            organization_id=fixture.organization_b_id,
            request_id=f"prospect-create-read-b-{uuid4()}",
        )
        async with app.tenant_prospect_unit_of_work(context_b) as unit_of_work:
            invisible = await unit_of_work.prospects.get(prospect.id)
            invisible_activity = await unit_of_work.activities.get(activity.id)
            invisible_task = await unit_of_work.tasks.get(task.id)

        async with owner.engine.connect() as connection:
            audit_count = await connection.scalar(
                text("SELECT count(*) FROM audit_events WHERE request_id = :request_id"),
                {"request_id": context.request_id},
            )
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert channel.value_normalized == "qa@example.ca"
    assert invisible is None
    assert invisible_activity is None
    assert invisible_task is None
    assert audit_count == 1


async def test_prospect_list_accepts_omitted_optional_filters() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_fixture(owner)
    now = datetime.now(UTC).replace(microsecond=0)
    context = tenant_context(fixture, request_id=f"prospect-list-default-filters-{uuid4()}")
    try:
        async with app.tenant_prospect_unit_of_work(context) as unit_of_work:
            prospect = await unit_of_work.prospects.add(
                ProspectDraft(
                    organization_id=fixture.organization_a_id,
                    internal_alias="Prospect liste QA",
                    origin=ProspectOrigin.MANUAL,
                    source_label="Saisie QA",
                ),
                now=now,
            )
            await unit_of_work.commit()

        async with app.tenant_prospect_unit_of_work(context) as unit_of_work:
            listed = await unit_of_work.prospects.list_active(limit=25)
            channels = await unit_of_work.contact_channels.list_for_prospect(prospect.id)
            duplicate = await unit_of_work.contact_channels.find_duplicate(
                channel_type="phone",
                value_normalized="+14185550100",
                prospect_id=prospect.id,
                contact_id=None,
            )
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert tuple(item.id for item in listed) == (prospect.id,)
    assert channels == ()
    assert duplicate is None


async def test_retention_lists_accept_omitted_optional_filters() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_fixture(owner)
    context = tenant_context(fixture, request_id=f"retention-list-default-filters-{uuid4()}")
    try:
        async with app.tenant_prospect_unit_of_work(context) as unit_of_work:
            policies = await unit_of_work.retention_policies.list(limit=25)
            reviews = await unit_of_work.retention_reviews.list(
                resource_type=None,
                review_state=None,
                due_before=None,
                limit=25,
            )
            holds = await unit_of_work.retention_holds.list(limit=25)
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert policies == ()
    assert reviews == ()
    assert holds == ()


async def test_unique_active_google_place_and_archive_version() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_fixture(owner)
    now = datetime.now(UTC).replace(microsecond=0)
    context = tenant_context(fixture, request_id=f"prospect-google-place-{uuid4()}")
    try:
        async with app.tenant_prospect_unit_of_work(context) as unit_of_work:
            first = await unit_of_work.prospects.add(
                ProspectDraft(
                    organization_id=fixture.organization_a_id,
                    internal_alias="Place A",
                    origin=ProspectOrigin.GOOGLE_PLACE,
                    source_label="Google Places",
                    google_place_id="place-123",
                ),
                now=now,
            )
            await unit_of_work.commit()

        with pytest.raises(OrganizationAdministrationUnavailable):
            async with app.tenant_prospect_unit_of_work(context) as unit_of_work:
                await unit_of_work.prospects.add(
                    ProspectDraft(
                        organization_id=fixture.organization_a_id,
                        internal_alias="Place A bis",
                        origin=ProspectOrigin.GOOGLE_PLACE,
                        source_label="Google Places",
                        google_place_id="place-123",
                    ),
                    now=now,
                )

        async with app.tenant_prospect_unit_of_work(context) as unit_of_work:
            archived = await unit_of_work.prospects.archive(first.id, expected_version=first.version, now=now)
            second = await unit_of_work.prospects.add(
                ProspectDraft(
                    organization_id=fixture.organization_a_id,
                    internal_alias="Place A retour",
                    origin=ProspectOrigin.GOOGLE_PLACE,
                    source_label="Google Places",
                    google_place_id="place-123",
                ),
                now=now,
            )
            await unit_of_work.commit()
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert archived is not None
    assert archived.archived_at is not None
    assert archived.version == first.version + 1
    assert second.id != first.id


async def test_contact_channel_requires_non_google_provenance_at_database_level() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_fixture(owner)
    now = datetime.now(UTC).replace(microsecond=0)
    context = tenant_context(fixture, request_id=f"prospect-google-provenance-{uuid4()}")
    try:
        async with app.tenant_prospect_unit_of_work(context) as unit_of_work:
            google_provenance = await unit_of_work.provenance.add(
                ProvenanceDraft(
                    organization_id=fixture.organization_a_id,
                    source_kind=ProvenanceSourceKind.GOOGLE_MAPS,
                    source_label="Google Places",
                    purpose="place_display",
                    obtained_at=now,
                ),
                now=now,
            )
            prospect = await unit_of_work.prospects.add(
                ProspectDraft(
                    organization_id=fixture.organization_a_id,
                    internal_alias="Entreprise avec provenance Google",
                    origin=ProspectOrigin.GOOGLE_PLACE,
                    source_label="Google Places",
                    google_place_id="place-google-provenance",
                ),
                now=now,
            )
            await unit_of_work.commit()

        with pytest.raises(DBAPIError):
            async with app.tenant_unit_of_work(context) as unit_of_work:
                await unit_of_work.session.execute(
                    text(
                        """
                        INSERT INTO contact_channels (
                            id, organization_id, prospect_id, channel_type, value,
                            value_normalized, provenance_id, purpose
                        )
                        VALUES (
                            :id, :organization_id, :prospect_id, 'email', 'secret@example.ca',
                            'secret@example.ca', :provenance_id, 'commercial_follow_up'
                        )
                        """
                    ),
                    {
                        "id": uuid4(),
                        "organization_id": fixture.organization_a_id,
                        "prospect_id": prospect.id,
                        "provenance_id": google_provenance.id,
                    },
                )
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()


async def test_prospect_compliance_migration_adds_contract_and_permission_guards() -> None:
    _app_url, owner_url = database_urls()
    owner = create_database(owner_url)
    try:
        async with owner.engine.connect() as connection:
            columns = set(
                (
                    await connection.scalars(
                        text(
                            """
                            SELECT table_name || '.' || column_name
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name IN (
                                  'source_providers', 'acquisition_records',
                                  'provenance_records', 'contact_permissions'
                              )
                              AND column_name IN (
                                  'allowed_territories', 'rights_attested_at',
                                  'data_categories', 'decision_reason_code',
                                  'acquisition_record_id', 'legal_basis_code',
                                  'valid_until', 'decided_by'
                              )
                            """
                        )
                    )
                ).all()
            )
            permission_unique = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM pg_constraint
                    WHERE conname = 'uq_contact_permissions_organization_id_channel_id'
                    """
                )
            )
            trigger_count = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM pg_trigger
                    WHERE tgname = 'contact_channels_ensure_unknown_permission'
                    """
                )
            )
    finally:
        await owner.close()

    assert {
        "source_providers.allowed_territories",
        "source_providers.rights_attested_at",
        "acquisition_records.data_categories",
        "acquisition_records.decision_reason_code",
        "provenance_records.acquisition_record_id",
        "contact_permissions.legal_basis_code",
        "contact_permissions.valid_until",
        "contact_permissions.decided_by",
    } <= columns
    assert permission_unique == 1
    assert trigger_count == 1


async def test_rollback_removes_prospect_and_audit_event() -> None:
    app_url, owner_url = database_urls()
    app = create_database(app_url)
    owner = create_database(owner_url)
    fixture = await create_fixture(owner)
    now = datetime.now(UTC).replace(microsecond=0)
    context = tenant_context(fixture, request_id=f"prospect-rollback-{uuid4()}")
    try:
        async with app.tenant_prospect_unit_of_work(context) as unit_of_work:
            prospect = await unit_of_work.prospects.add(
                ProspectDraft(
                    organization_id=fixture.organization_a_id,
                    internal_alias="Rollback QA",
                    origin=ProspectOrigin.MANUAL,
                    source_label="Saisie QA",
                ),
                now=now,
            )
            await unit_of_work.audit.record(
                AuditEventDraft(
                    id=uuid4(),
                    scope=AuditScope.TENANT,
                    action=AuditAction.PROSPECT_CREATED,
                    entity_type="prospect",
                    entity_id=prospect.id,
                    actor_kind=AuditActorKind.USER,
                    actor_id=fixture.actor_a_id,
                    organization_id=fixture.organization_a_id,
                    request_id=context.request_id,
                    correlation_id=context.request_id,
                    source=AuditSource.API,
                    metadata={"origin": "manual"},
                )
            )
            await unit_of_work.rollback()

        async with owner.engine.connect() as connection:
            prospect_count = await connection.scalar(
                text("SELECT count(*) FROM prospects WHERE id = :prospect_id"),
                {"prospect_id": prospect.id},
            )
            audit_count = await connection.scalar(
                text("SELECT count(*) FROM audit_events WHERE request_id = :request_id"),
                {"request_id": context.request_id},
            )
    finally:
        await delete_fixture(owner, fixture)
        await app.close()
        await owner.close()

    assert prospect_count == 0
    assert audit_count == 0
