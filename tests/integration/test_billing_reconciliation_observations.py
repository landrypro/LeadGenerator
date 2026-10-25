"""Persistance atomique et séparation des privilèges des observations P53-08."""

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from backend.app.application.errors import BillingOperationError
from backend.app.application.ports.billing import BillingReconciliationDifferenceCode, NormalizedSubscriptionSnapshot
from backend.app.application.tenancy import ActorContext
from backend.app.application.use_cases.billing_reconciliation import (
    BillingReconciliationClassifier,
    BillingReconciliationInspection,
    BillingReconciliationRunProcessor,
    ReconciliationCandidate,
    ReconciliationLease,
    ReconciliationReadStatus,
    ReconciliationReason,
    ReconciliationRunResult,
    ReconciliationScheduleKind,
    ReconciliationWindow,
)
from backend.app.domain.billing import BillingPeriod, BillingProvider, SubscriptionState
from backend.app.domain.catalog import CurrencyCode
from backend.app.infrastructure.billing import SimulatedBillingProviderGateway
from backend.app.infrastructure.postgres import PostgresDatabase
from backend.app.infrastructure.postgres.billing_reconciliation import (
    PostgresBillingManualReconciliationRepository,
    PostgresBillingReconciliationLeaseRepository,
    PostgresBillingReconciliationScheduleRepository,
    PostgresSimulatedBillingSubscriptionReader,
)

pytestmark = pytest.mark.integration


def _database(url: str) -> PostgresDatabase:
    return PostgresDatabase(
        url,
        connect_timeout_seconds=10,
        pool_size=3,
        max_overflow=0,
        pool_timeout_seconds=10,
        statement_timeout_ms=10000,
    )


async def test_lease_is_exclusive_and_expired_worker_cannot_renew() -> None:
    worker_url = os.environ.get("TEST_WORKER_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not worker_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_WORKER_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("Les URL PostgreSQL worker et propriétaire sont requises.")
    worker, owner = _database(worker_url), _database(owner_url)
    run_id = uuid4()
    repository = PostgresBillingReconciliationLeaseRepository(worker.session_factory)
    try:
        async with owner.engine.begin() as connection:
            existing = await connection.scalar(
                text("SELECT count(*) FROM billing_reconciliation_runs WHERE status IN ('pending','running')")
            )
            assert existing == 0, "Ce test exige une base jetable sans exécution active."
            await connection.execute(
                text(
                    "INSERT INTO billing_reconciliation_runs "
                    "(id,run_kind,status,window_started_at,window_ended_at) "
                    "VALUES (:id,'incremental','pending',clock_timestamp()-interval '15 minutes',clock_timestamp())"
                ),
                {"id": run_id},
            )
        first, concurrent = await asyncio.gather(repository.claim(), repository.claim())
        claimed = [lease for lease in (first, concurrent) if lease is not None]
        assert len(claimed) == 1
        old = claimed[0]
        assert old.run_id == run_id and old.organization_id is None
        assert await repository.renew(lease=old)
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE billing_reconciliation_runs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=:id"
                ),
                {"id": run_id},
            )
        assert not await repository.renew(lease=old)
        recovered = await repository.claim()
        assert recovered is not None and recovered.run_id == run_id and recovered.token != old.token
        assert not await repository.renew(lease=old)
        assert not await repository.release(lease=old)
        assert await repository.renew(lease=recovered)
        assert await repository.release(lease=recovered)
        resumed = await repository.claim()
        assert resumed is not None and resumed.token != recovered.token
        assert not await repository.release(lease=recovered)
        async with owner.engine.connect() as connection:
            app_allowed = await connection.scalar(
                text(
                    "SELECT has_function_privilege('prospect_app','app_private.claim_billing_reconciliation_run()','EXECUTE')"
                )
            )
        assert app_allowed is False
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(text("DELETE FROM billing_reconciliation_runs WHERE id=:id"), {"id": run_id})
        await worker.close()
        await owner.close()


async def test_manual_request_is_authorized_scoped_idempotent_and_audited() -> None:
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    worker_url = os.environ.get("TEST_WORKER_DATABASE_URL", "")
    if not app_url or not owner_url or not worker_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("Les URL PostgreSQL application et propriétaire sont obligatoires.")
        pytest.skip("Les URL PostgreSQL application et propriétaire sont requises.")
    app, owner, worker_db = _database(app_url), _database(owner_url), _database(worker_url)
    actor, ordinary, org, other = (uuid4() for _ in range(4))
    params = {
        "actor": actor,
        "ordinary": ordinary,
        "org": org,
        "other": other,
        "actor_email": f"manual-{actor}@example.test",
        "ordinary_email": f"manual-{ordinary}@example.test",
    }
    repository = PostgresBillingManualReconciliationRepository(app.actor_unit_of_work)
    key = "a" * 64
    lease_token = uuid4()
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO users (id,email,email_normalized,display_name,password_hash,status,platform_role) "
                    "VALUES (:actor,:actor_email,:actor_email,'Admin','hash','active','platform_admin'),"
                    "(:ordinary,:ordinary_email,:ordinary_email,'User','hash','active',NULL)"
                ),
                params,
            )
            await connection.execute(
                text(
                    "INSERT INTO organizations (id,name,timezone,status,created_by,activated_at) "
                    "VALUES (:org,'Manual','America/Toronto','active',:actor,clock_timestamp()),"
                    "(:other,'Other','America/Toronto','active',:actor,clock_timestamp())"
                ),
                params,
            )
        context = ActorContext(actor, "manual-reconciliation-test")
        first, second = await asyncio.gather(
            *(
                repository.request(
                    context=context, organization_id=org, reason=ReconciliationReason.STATE_MISMATCH, key_digest=key
                )
                for _ in range(2)
            )
        )
        assert first == second
        with pytest.raises(BillingOperationError):
            await repository.request(
                context=context, organization_id=other, reason=ReconciliationReason.STATE_MISMATCH, key_digest=key
            )
        with pytest.raises(BillingOperationError):
            await repository.request(
                context=ActorContext(ordinary, "unauthorized-manual"),
                organization_id=org,
                reason=ReconciliationReason.OPERATOR_REVIEW,
                key_digest="b" * 64,
            )
        async with owner.engine.connect() as connection:
            count = await connection.scalar(
                text("SELECT count(*) FROM billing_reconciliation_runs WHERE requested_by=:actor"), params
            )
            audit = await connection.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE actor_id=:actor AND action='billing.reconciliation_requested' AND metadata->>'reason_code'='state_mismatch'"
                ),
                params,
            )
        assert count == 1 and audit == 1
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE billing_reconciliation_runs SET status='running',started_at=clock_timestamp(),lease_token=:token,"
                    "lease_expires_at=clock_timestamp()+interval '2 minutes' WHERE id=:run"
                ),
                {"run": first, "token": lease_token},
            )
        leases = PostgresBillingReconciliationLeaseRepository(worker_db.session_factory)
        provider = SimulatedBillingProviderGateway(webhook_secret=b"synthetic-secret-for-reconciliation-test")
        processor = BillingReconciliationRunProcessor(
            provider=BillingProvider.SIMULATED,
            inspection=BillingReconciliationInspection(provider, BillingReconciliationClassifier()),
            repository=leases,
        )
        assert (
            await processor.process(lease=ReconciliationLease(first, lease_token, org))
            is ReconciliationRunResult.COMPLETED
        )
        async with owner.engine.connect() as connection:
            status = await connection.scalar(
                text("SELECT status FROM billing_reconciliation_runs WHERE id=:id"), {"id": first}
            )
        assert status == "completed"
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    "DELETE FROM audit_events WHERE actor_id IN (:actor,:ordinary) AND action='billing.reconciliation_requested'"
                ),
                params,
            )
            await connection.execute(
                text("DELETE FROM billing_reconciliation_runs WHERE requested_by IN (:actor,:ordinary)"), params
            )
            await connection.execute(text("DELETE FROM organizations WHERE id IN (:org,:other)"), params)
            await connection.execute(text("DELETE FROM users WHERE id IN (:actor,:ordinary)"), params)
        await app.close()
        await owner.close()
        await worker_db.close()


async def test_observation_is_scoped_idempotent_and_rejects_stale_versions() -> None:
    worker_url = os.environ.get("TEST_WORKER_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not worker_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_WORKER_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("Les URL PostgreSQL worker et propriétaire sont requises.")
    worker, owner = _database(worker_url), _database(owner_url)
    actor, approver, org, other_org, plan, version, customer, sub, run = (uuid4() for _ in range(9))
    now = datetime.now(UTC).replace(microsecond=0)
    params = {
        "actor": actor,
        "approver": approver,
        "org": org,
        "other_org": other_org,
        "plan": plan,
        "version": version,
        "customer": customer,
        "sub": sub,
        "run": run,
        "now": now,
        "end": now + timedelta(days=30),
        "actor_email": f"recon-{actor}@example.test",
        "approver_email": f"recon-{approver}@example.test",
    }
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO users (id,email,email_normalized,display_name,password_hash,status,created_at,updated_at) VALUES (:actor,:actor_email,:actor_email,'Reconciliation','hash','active',:now,:now),(:approver,:approver_email,:approver_email,'Approval','hash','active',:now,:now)"
                ),
                params,
            )
            await connection.execute(
                text(
                    "INSERT INTO organizations (id,name,timezone,status,created_by,activated_at,created_at,updated_at) VALUES (:org,'Reconciliation','America/Toronto','active',:actor,:now,:now,:now),(:other_org,'Other','America/Toronto','active',:actor,:now,:now,:now)"
                ),
                params,
            )
            await connection.execute(
                text("INSERT INTO plan_catalog (id,code,state) VALUES (:plan,'custom','draft')"), params
            )
            await connection.execute(
                text(
                    "INSERT INTO plan_versions (id,plan_id,version_number,state,currency,billing_cycle,amount_excluding_tax_minor,effective_from,created_by_user_id,approved_by_user_id,published_at) VALUES (:version,:plan,1,'published','CAD','monthly',0,:now,:actor,:approver,:now)"
                ),
                params,
            )
            await connection.execute(
                text(
                    "INSERT INTO billing_customers (id,organization_id,provider,provider_customer_reference) VALUES (:customer,:org,'simulated',:customer_ref)"
                ),
                {**params, "customer_ref": f"customer-{customer}"},
            )
            await connection.execute(
                text(
                    "INSERT INTO subscriptions (id,organization_id,billing_customer_id,provider,provider_subscription_reference,plan_version_id,currency,state,current_period_start,current_period_end,provider_updated_at) VALUES (:sub,:org,:customer,'simulated',:subscription_ref,:version,'CAD','pending_checkout',:now,:end,:now)"
                ),
                {**params, "subscription_ref": f"subscription-{sub}"},
            )
            await connection.execute(
                text(
                    "INSERT INTO billing_reconciliation_runs (id,organization_id,run_kind,status,window_started_at,window_ended_at) VALUES (:run,:org,'manual','pending',:now,:end)"
                ),
                params,
            )

        snapshot = NormalizedSubscriptionSnapshot(
            f"subscription-{sub}",
            f"customer-{customer}",
            SubscriptionState.PENDING_CHECKOUT,
            CurrencyCode.CAD,
            "sim_price",
            BillingPeriod(now, now + timedelta(days=30)),
            False,
            now,
        )
        candidate = ReconciliationCandidate(run, org, sub, 1, snapshot)
        repository = PostgresBillingReconciliationLeaseRepository(worker.session_factory)
        lease = await repository.claim()
        assert lease is not None and lease.run_id == run
        read = await repository.read_next(lease=lease)
        assert read.status is ReconciliationReadStatus.CANDIDATE
        assert read.candidate is not None and read.candidate.subscription_id == sub
        assert read.candidate.snapshot.currency is CurrencyCode.CAD
        assert not await repository.complete(lease=lease)
        stale_lease = ReconciliationLease(run, uuid4(), org)
        assert (await repository.read_next(lease=stale_lease)).status is ReconciliationReadStatus.LEASE_LOST
        assert not await repository.record_and_advance(
            lease=stale_lease, candidate=candidate, difference=BillingReconciliationDifferenceCode.UNRESOLVED
        )
        results = await asyncio.gather(
            *(
                repository.record_and_advance(
                    lease=lease, candidate=candidate, difference=BillingReconciliationDifferenceCode.UNRESOLVED
                )
                for _ in range(2)
            )
        )
        assert results == [True, True]
        assert not await repository.record_and_advance(
            lease=lease, candidate=candidate, difference=BillingReconciliationDifferenceCode.IN_SYNC
        )
        assert not await repository.record_and_advance(
            lease=lease,
            candidate=ReconciliationCandidate(run, other_org, sub, 1, snapshot),
            difference=BillingReconciliationDifferenceCode.UNRESOLVED,
        )
        assert not await repository.record_and_advance(
            lease=lease,
            candidate=ReconciliationCandidate(run, org, sub, 2, snapshot),
            difference=BillingReconciliationDifferenceCode.UNRESOLVED,
        )
        assert (await repository.read_next(lease=lease)).status is ReconciliationReadStatus.EXHAUSTED
        assert await repository.complete(lease=lease)
        assert not await repository.complete(lease=lease)
        async with owner.engine.connect() as connection:
            count = await connection.scalar(
                text("SELECT count(*) FROM billing_reconciliation_differences WHERE run_id=:run"), params
            )
            audit_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE organization_id=:org AND action='billing.reconciliation_difference_detected' AND metadata->>'difference_code'='unresolved'"
                ),
                params,
            )
            privilege = await connection.scalar(
                text(
                    "SELECT has_function_privilege('prospect_app','app_private.advance_billing_reconciliation_run(uuid,uuid,uuid,uuid,integer,text)','EXECUTE')"
                )
            )
        assert count == 1
        assert audit_count == 1
        assert privilege is False
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    "DELETE FROM audit_events WHERE organization_id=:org AND action='billing.reconciliation_difference_detected'"
                ),
                params,
            )
            await connection.execute(text("DELETE FROM billing_reconciliation_differences WHERE run_id=:run"), params)
            await connection.execute(text("DELETE FROM billing_reconciliation_runs WHERE id=:run"), params)
            await connection.execute(text("DELETE FROM subscriptions WHERE id=:sub"), params)
            await connection.execute(text("DELETE FROM billing_customers WHERE id=:customer"), params)
            await connection.execute(text("UPDATE plan_versions SET state='superseded' WHERE id=:version"), params)
            await connection.execute(text("DELETE FROM plan_versions WHERE id=:version"), params)
            await connection.execute(text("DELETE FROM plan_catalog WHERE id=:plan"), params)
            await connection.execute(text("DELETE FROM organizations WHERE id IN (:org,:other_org)"), params)
            await connection.execute(text("DELETE FROM users WHERE id IN (:actor,:approver)"), params)
        await worker.close()
        await owner.close()


async def test_scheduled_windows_are_idempotent_and_refuse_gaps() -> None:
    worker_url = os.environ.get("TEST_WORKER_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    if not worker_url or not owner_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("TEST_WORKER_DATABASE_URL et TEST_MIGRATION_DATABASE_URL sont obligatoires.")
        pytest.skip("Les URL PostgreSQL worker et propriétaire sont requises.")
    worker, owner = _database(worker_url), _database(owner_url)
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(days=5)
    duration = timedelta(minutes=15)
    window = ReconciliationWindow(ReconciliationScheduleKind.INCREMENTAL, end - duration, end)
    repository = PostgresBillingReconciliationScheduleRepository(worker.session_factory)
    created_ids = []
    try:
        async with owner.engine.connect() as connection:
            existing = await connection.scalar(
                text(
                    "SELECT count(*) FROM billing_reconciliation_runs WHERE organization_id IS NULL AND run_kind='incremental'"
                )
            )
        assert existing == 0, "Ce test exige une base jetable sans exécution globale préexistante."
        first, replay = await asyncio.gather(
            repository.schedule_window(window=window), repository.schedule_window(window=window)
        )
        assert first is not None and first == replay
        created_ids.append(first)
        gap = ReconciliationWindow(ReconciliationScheduleKind.INCREMENTAL, end + duration, end + 2 * duration)
        assert await repository.schedule_window(window=gap) is None
        following = ReconciliationWindow(ReconciliationScheduleKind.INCREMENTAL, end, end + duration)
        next_id = await repository.schedule_window(window=following)
        assert next_id is not None and next_id != first
        created_ids.append(next_id)
        async with owner.engine.connect() as connection:
            allowed = await connection.scalar(
                text(
                    "SELECT has_function_privilege('prospect_app','app_private.schedule_billing_reconciliation_window(text,timestamptz,timestamptz)','EXECUTE')"
                )
            )
        assert allowed is False
    finally:
        async with owner.engine.begin() as connection:
            for run_id in created_ids:
                await connection.execute(text("DELETE FROM billing_reconciliation_runs WHERE id=:id"), {"id": run_id})
        await worker.close()
        await owner.close()


@pytest.mark.parametrize("currency", list(CurrencyCode))
@pytest.mark.parametrize("matching_price", [True, False], ids=["proven-local-stale", "price-mismatch"])
async def test_shared_simulator_evidence_is_restart_safe_and_only_corrects_proven_local_stale(
    currency: CurrencyCode, matching_price: bool
) -> None:
    worker_url = os.environ.get("TEST_WORKER_DATABASE_URL", "")
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    app_url = os.environ.get("TEST_DATABASE_URL", "")
    if not worker_url or not owner_url or not app_url:
        if os.environ.get("REQUIRE_INFRASTRUCTURE_TESTS", "").lower() == "true":
            pytest.fail("Les URL PostgreSQL application, worker et propriétaire sont obligatoires.")
        pytest.skip("Les URL PostgreSQL application, worker et propriétaire sont requises.")
    worker, owner, app = _database(worker_url), _database(owner_url), _database(app_url)
    actor, approver, org, plan, version, customer, subscription, run, inbox, lease_token = (uuid4() for _ in range(10))
    now = datetime.now(UTC).replace(microsecond=0)
    provider_time = now + timedelta(seconds=1)
    customer_reference = f"sim_customer_{customer.hex}"
    subscription_reference = f"sim_subscription_{subscription.hex}"
    expected_price = f"sim_price_{version.hex}"
    provider_price = expected_price if matching_price else "sim_price_incompatible"
    event_id = f"sim_event_{inbox.hex}"
    payload = {
        "schema_version": 1,
        "provider_object_reference": subscription_reference,
        "subscription": {
            "reference": subscription_reference,
            "customer_reference": customer_reference,
            "state": "active",
            "currency": currency.value,
            "price_reference": provider_price,
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=30)).isoformat(),
            "cancel_at_period_end": False,
            "updated_at": provider_time.isoformat(),
        },
    }
    params = {
        "actor": actor,
        "approver": approver,
        "org": org,
        "plan": plan,
        "version": version,
        "customer": customer,
        "subscription": subscription,
        "run": run,
        "inbox": inbox,
        "lease_token": lease_token,
        "now": now,
        "provider_time": provider_time,
        "end": now + timedelta(days=30),
        "currency": currency.value,
        "customer_reference": customer_reference,
        "subscription_reference": subscription_reference,
        "event_id": event_id,
        "payload": json.dumps(payload, separators=(",", ":")),
        "digest": "a" * 64,
        "actor_email": f"shared-reconciliation-{actor}@example.test",
        "approver_email": f"shared-reconciliation-{approver}@example.test",
    }
    try:
        async with owner.engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO users (id,email,email_normalized,display_name,password_hash,status) VALUES "
                    "(:actor,:actor_email,:actor_email,'Reconciliation','hash','active'),"
                    "(:approver,:approver_email,:approver_email,'Approver','hash','active')"
                ),
                params,
            )
            await connection.execute(
                text(
                    "INSERT INTO organizations (id,name,timezone,status,created_by,activated_at) "
                    "VALUES (:org,'Shared simulator','America/Toronto','active',:actor,:now)"
                ),
                params,
            )
            await connection.execute(
                text("INSERT INTO plan_catalog (id,code,state) VALUES (:plan,'custom','published')"), params
            )
            await connection.execute(
                text(
                    "INSERT INTO plan_versions (id,plan_id,version_number,state,currency,billing_cycle,"
                    "amount_excluding_tax_minor,effective_from,created_by_user_id,approved_by_user_id,published_at) "
                    "VALUES (:version,:plan,1,'published',:currency,'monthly',0,:now,:actor,:approver,:now)"
                ),
                params,
            )
            await connection.execute(
                text(
                    "INSERT INTO billing_customers (id,organization_id,provider,provider_customer_reference) "
                    "VALUES (:customer,:org,'simulated',:customer_reference)"
                ),
                params,
            )
            await connection.execute(
                text(
                    "INSERT INTO subscriptions (id,organization_id,billing_customer_id,provider,"
                    "provider_subscription_reference,plan_version_id,currency,state,current_period_start,"
                    "current_period_end,provider_updated_at,created_at) VALUES (:subscription,:org,:customer,'simulated',"
                    ":subscription_reference,:version,:currency,'pending_checkout',:now,:end,:now,"
                    "clock_timestamp()-interval '1 minute')"
                ),
                params,
            )
            await connection.execute(
                text(
                    "INSERT INTO billing_event_inbox (id,provider,provider_event_id,event_type,"
                    "provider_object_reference,provider_created_at,received_at,payload_digest,signature_version,"
                    "api_version,normalized_payload,status) VALUES (:inbox,'simulated',:event_id,'invoice.paid',"
                    ":subscription_reference,:provider_time,:provider_time,:digest,1,'normalized-v1',"
                    "CAST(:payload AS jsonb),'admitted')"
                ),
                params,
            )
            await connection.execute(
                text(
                    "INSERT INTO billing_reconciliation_runs (id,organization_id,run_kind,status,"
                    "window_started_at,window_ended_at,started_at,lease_token,lease_expires_at) "
                    "VALUES (:run,:org,'manual','running',:now,:end,clock_timestamp(),:lease_token,"
                    "clock_timestamp()+interval '2 minutes')"
                ),
                params,
            )
        async with app.session_factory.begin() as session:
            assert await session.scalar(
                text("SELECT app_private.record_simulated_billing_webhook_snapshot('simulated',:event_id)"),
                params,
            )
        reader = PostgresSimulatedBillingSubscriptionReader(worker.session_factory)
        snapshot = await reader.get_subscription(provider_subscription_reference=subscription_reference)
        assert snapshot.state is SubscriptionState.ACTIVE
        assert snapshot.currency is currency
        leases = PostgresBillingReconciliationLeaseRepository(worker.session_factory)
        processor = BillingReconciliationRunProcessor(
            provider=BillingProvider.SIMULATED,
            inspection=BillingReconciliationInspection(reader, BillingReconciliationClassifier()),
            repository=leases,
        )
        lease = ReconciliationLease(run, lease_token, org)
        candidate_read = await leases.read_next(lease=lease)
        assert candidate_read.status is ReconciliationReadStatus.CANDIDATE
        assert candidate_read.candidate is not None and candidate_read.candidate.subscription_id == subscription
        assert await processor.process(lease=lease) is ReconciliationRunResult.COMPLETED
        async with owner.engine.connect() as connection:
            result = (
                (
                    await connection.execute(
                        text(
                            "SELECT s.state,d.difference_code,d.resolved_at,"
                            "(SELECT count(*) FROM audit_events a WHERE a.organization_id=:org "
                            "AND a.action='billing.reconciliation_correction_applied') AS corrections,"
                            "(SELECT count(*) FROM billing_events e WHERE e.inbox_id=:inbox) AS events,"
                            "(SELECT count(*) FROM subscription_transitions t WHERE t.subscription_id=:subscription) "
                            "AS transitions FROM subscriptions s JOIN billing_reconciliation_differences d "
                            "ON d.subscription_id=s.id WHERE s.id=:subscription AND d.run_id=:run"
                        ),
                        params,
                    )
                )
                .mappings()
                .one()
            )
            direct_worker_table_access = await connection.scalar(
                text(
                    "SELECT has_table_privilege('prospect_worker',"
                    "'public.simulated_billing_provider_subscriptions','SELECT')"
                )
            )
        if matching_price:
            assert result["state"] == "active"
            assert result["difference_code"] == "local_stale"
            assert result["resolved_at"] is not None
            assert (result["corrections"], result["events"], result["transitions"]) == (1, 1, 1)
        else:
            assert result["state"] == "pending_checkout"
            assert result["difference_code"] == "price_mismatch"
            assert result["resolved_at"] is None
            assert (result["corrections"], result["events"], result["transitions"]) == (0, 0, 0)
        assert direct_worker_table_access is False
    finally:
        async with owner.engine.begin() as connection:
            await connection.execute(text("DELETE FROM audit_events WHERE organization_id=:org"), params)
            await connection.execute(
                text("DELETE FROM subscription_transitions WHERE subscription_id=:subscription"), params
            )
            await connection.execute(text("DELETE FROM billing_events WHERE inbox_id=:inbox"), params)
            await connection.execute(text("DELETE FROM billing_reconciliation_differences WHERE run_id=:run"), params)
            await connection.execute(text("DELETE FROM billing_reconciliation_runs WHERE id=:run"), params)
            await connection.execute(
                text(
                    "DELETE FROM simulated_billing_provider_subscriptions "
                    "WHERE provider_subscription_reference=:subscription_reference"
                ),
                params,
            )
            await connection.execute(text("DELETE FROM billing_event_inbox WHERE id=:inbox"), params)
            await connection.execute(text("DELETE FROM subscriptions WHERE id=:subscription"), params)
            await connection.execute(text("DELETE FROM billing_customers WHERE id=:customer"), params)
            await connection.execute(text("UPDATE plan_versions SET state='superseded' WHERE id=:version"), params)
            await connection.execute(text("DELETE FROM plan_versions WHERE id=:version"), params)
            await connection.execute(text("DELETE FROM plan_catalog WHERE id=:plan"), params)
            await connection.execute(text("DELETE FROM organizations WHERE id=:org"), params)
            await connection.execute(text("DELETE FROM users WHERE id IN (:actor,:approver)"), params)
        await app.close()
        await worker.close()
        await owner.close()
