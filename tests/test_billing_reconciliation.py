from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from backend.app.application.ports.billing import (
    BillingCheckoutCommand,
    BillingReconciliationDifferenceCode,
    BillingReturnTarget,
    NormalizedBillingEvent,
    NormalizedSubscriptionSnapshot,
)
from backend.app.application.use_cases.billing_reconciliation import (
    BillingReconciliationClassifier,
    BillingReconciliationInspection,
    BillingReconciliationObserver,
    BillingReconciliationRunProcessor,
    BillingReconciliationScheduler,
    BillingReconciliationWorker,
    ReconciliationCandidate,
    ReconciliationLease,
    ReconciliationRead,
    ReconciliationReadStatus,
    ReconciliationRunResult,
    ReconciliationScheduleKind,
    ReconciliationWindow,
    is_reconciliation_correction_candidate,
    next_reconciliation_window,
)
from backend.app.domain.billing import BillingEventType, BillingPeriod, BillingProvider, SubscriptionState
from backend.app.domain.catalog import CurrencyCode
from backend.app.infrastructure.billing import SimulatedBillingProviderGateway, SimulatedWebhookScenario

_NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


class _RunRepository:
    def __init__(self, candidates: list[ReconciliationCandidate]) -> None:
        self.candidates = list(candidates)
        self.observations: list[BillingReconciliationDifferenceCode] = []
        self.lease_valid = True
        self.reject_record = False
        self.reject_complete = False
        self.completed = False

    async def read_next(self, *, lease: ReconciliationLease) -> ReconciliationRead:
        del lease
        if not self.lease_valid:
            return ReconciliationRead(ReconciliationReadStatus.LEASE_LOST)
        if not self.candidates:
            return ReconciliationRead(ReconciliationReadStatus.EXHAUSTED)
        return ReconciliationRead(ReconciliationReadStatus.CANDIDATE, self.candidates[0])

    async def record_and_advance(
        self,
        *,
        lease: ReconciliationLease,
        candidate: ReconciliationCandidate,
        difference: BillingReconciliationDifferenceCode,
    ) -> bool:
        del lease
        if not self.lease_valid or self.reject_record or self.candidates[0] != candidate:
            return False
        self.candidates.pop(0)
        self.observations.append(difference)
        return True

    async def complete(self, *, lease: ReconciliationLease) -> bool:
        del lease
        if not self.lease_valid or self.reject_complete or self.candidates:
            return False
        self.completed = True
        return True


def _snapshot(currency: CurrencyCode = CurrencyCode.CAD) -> NormalizedSubscriptionSnapshot:
    return NormalizedSubscriptionSnapshot(
        provider_subscription_reference="sim_subscription_1",
        provider_customer_reference="sim_customer_1",
        state=SubscriptionState.PENDING_CHECKOUT,
        currency=currency,
        provider_price_reference="sim_price_1",
        period=BillingPeriod(_NOW, _NOW + timedelta(days=30)),
        cancel_at_period_end=False,
        provider_updated_at=_NOW,
    )


def _processor(repository: _RunRepository) -> BillingReconciliationRunProcessor:
    provider = SimulatedBillingProviderGateway(webhook_secret=b"synthetic-secret-for-reconciliation-test")
    return BillingReconciliationRunProcessor(
        provider=BillingProvider.SIMULATED,
        inspection=BillingReconciliationInspection(provider, BillingReconciliationClassifier()),
        repository=repository,
    )


@pytest.mark.asyncio
async def test_run_processor_bounds_work_and_resumes_without_duplicate_observations() -> None:
    lease = ReconciliationLease(uuid4(), uuid4(), uuid4())
    candidates = [
        ReconciliationCandidate(lease.run_id, lease.organization_id, uuid4(), 1, _snapshot()) for _ in range(2)
    ]
    repository = _RunRepository(candidates)
    processor = _processor(repository)

    assert await processor.process(lease=lease, batch_size=1) is ReconciliationRunResult.YIELDED
    assert not repository.completed
    assert await processor.process(lease=lease, batch_size=2) is ReconciliationRunResult.COMPLETED
    assert repository.observations == [BillingReconciliationDifferenceCode.UNRESOLVED] * 2
    assert repository.completed


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["lease", "version", "completion"])
async def test_run_processor_never_completes_after_lost_lease_or_conflict(failure: str) -> None:
    lease = ReconciliationLease(uuid4(), uuid4(), None)
    candidates = (
        [] if failure == "completion" else [ReconciliationCandidate(lease.run_id, uuid4(), uuid4(), 1, _snapshot())]
    )
    repository = _RunRepository(candidates)
    repository.lease_valid = failure != "lease"
    repository.reject_record = failure == "version"
    repository.reject_complete = failure == "completion"

    assert await _processor(repository).process(lease=lease) is ReconciliationRunResult.LEASE_OR_VERSION_CONFLICT
    assert not repository.completed
    assert not repository.observations
    assert len(repository.candidates) == len(candidates)


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_scope", ["run", "organization"])
async def test_run_processor_rejects_candidates_outside_scope(wrong_scope: str) -> None:
    lease = ReconciliationLease(uuid4(), uuid4(), uuid4())
    candidate = ReconciliationCandidate(
        uuid4() if wrong_scope == "run" else lease.run_id,
        uuid4() if wrong_scope == "organization" else lease.organization_id,
        uuid4(),
        1,
        _snapshot(),
    )
    repository = _RunRepository([candidate])
    with pytest.raises(ValueError, match="candidat"):
        await _processor(repository).process(lease=lease)
    assert not repository.observations


def test_run_processor_rejects_real_provider_and_invalid_read_contract() -> None:
    provider = SimulatedBillingProviderGateway(webhook_secret=b"synthetic-secret-for-reconciliation-test")
    with pytest.raises(ValueError, match="simulateur"):
        BillingReconciliationRunProcessor(
            provider=BillingProvider.STRIPE,
            inspection=BillingReconciliationInspection(provider, BillingReconciliationClassifier()),
            repository=_RunRepository([]),
        )
    with pytest.raises(ValueError, match="candidat"):
        ReconciliationRead(ReconciliationReadStatus.CANDIDATE)


@pytest.mark.asyncio
async def test_run_processor_rechecks_lease_after_provider_read() -> None:
    lease = ReconciliationLease(uuid4(), uuid4(), None)
    candidate = ReconciliationCandidate(lease.run_id, uuid4(), uuid4(), 1, _snapshot())
    repository = _RunRepository([candidate])
    provider = SimulatedBillingProviderGateway(webhook_secret=b"synthetic-secret-for-reconciliation-test")

    class LosingLeaseInspection(BillingReconciliationInspection):
        async def inspect(self, *, local: NormalizedSubscriptionSnapshot | None) -> BillingReconciliationDifferenceCode:
            result = await super().inspect(local=local)
            repository.lease_valid = False
            return result

    processor = BillingReconciliationRunProcessor(
        provider=BillingProvider.SIMULATED,
        inspection=LosingLeaseInspection(provider, BillingReconciliationClassifier()),
        repository=repository,
    )
    assert await processor.process(lease=lease) is ReconciliationRunResult.LEASE_OR_VERSION_CONFLICT
    assert repository.candidates == [candidate]
    assert not repository.observations
    assert not repository.completed


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_size", [0, 101])
async def test_run_processor_rejects_unbounded_batches(batch_size: int) -> None:
    with pytest.raises(ValueError, match="taille du lot"):
        await _processor(_RunRepository([])).process(
            lease=ReconciliationLease(uuid4(), uuid4(), None), batch_size=batch_size
        )


@pytest.mark.asyncio
async def test_worker_releases_bounded_batch_for_safe_continuation() -> None:
    lease = ReconciliationLease(uuid4(), uuid4(), None)
    repository = _RunRepository(
        [ReconciliationCandidate(lease.run_id, uuid4(), uuid4(), 1, _snapshot()) for _ in range(101)]
    )

    class Leases:
        released = False

        async def claim(self) -> ReconciliationLease | None:
            return lease

        async def release(self, *, lease: ReconciliationLease) -> bool:
            self.released = True
            return True

    leases = Leases()
    assert await BillingReconciliationWorker(leases=leases, processor=_processor(repository)).run_once()
    assert leases.released
    assert len(repository.observations) == 100
    assert len(repository.candidates) == 1
    assert not repository.completed


@pytest.mark.asyncio
async def test_worker_does_not_release_after_unexpected_failure() -> None:
    lease = ReconciliationLease(uuid4(), uuid4(), None)
    candidate = ReconciliationCandidate(uuid4(), uuid4(), uuid4(), 1, _snapshot())

    class Leases:
        released = False

        async def claim(self) -> ReconciliationLease | None:
            return lease

        async def release(self, *, lease: ReconciliationLease) -> bool:
            self.released = True
            return True

    leases = Leases()
    with pytest.raises(ValueError, match="exécution"):
        await BillingReconciliationWorker(leases=leases, processor=_processor(_RunRepository([candidate]))).run_once()
    assert not leases.released


@pytest.mark.asyncio
@pytest.mark.parametrize("currency", list(CurrencyCode))
async def test_identical_snapshots_are_in_sync_for_each_currency(currency: CurrencyCode) -> None:
    snapshot = _snapshot(currency)
    result = await BillingReconciliationClassifier().classify_difference(local=snapshot, provider=snapshot)
    assert result is BillingReconciliationDifferenceCode.IN_SYNC


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"provider_customer_reference": "other"}, BillingReconciliationDifferenceCode.MAPPING_MISSING),
        ({"provider_subscription_reference": "other"}, BillingReconciliationDifferenceCode.MAPPING_MISSING),
        ({"provider_price_reference": ""}, BillingReconciliationDifferenceCode.MAPPING_MISSING),
        ({"currency": CurrencyCode.USD}, BillingReconciliationDifferenceCode.CURRENCY_MISMATCH),
        ({"provider_price_reference": "other"}, BillingReconciliationDifferenceCode.PRICE_MISMATCH),
        ({"state": SubscriptionState.ACTIVE}, BillingReconciliationDifferenceCode.UNRESOLVED),
        (
            {"state": SubscriptionState.ACTIVE, "provider_updated_at": _NOW + timedelta(seconds=1)},
            BillingReconciliationDifferenceCode.LOCAL_STALE,
        ),
        (
            {"state": SubscriptionState.ACTIVE, "provider_updated_at": _NOW - timedelta(seconds=1)},
            BillingReconciliationDifferenceCode.PROVIDER_STALE,
        ),
        ({"provider_updated_at": datetime(2026, 10, 22, 12)}, BillingReconciliationDifferenceCode.UNRESOLVED),
    ],
)
async def test_classification_fails_closed_for_divergence(changes: dict[str, object], expected: object) -> None:
    local = _snapshot()
    provider = replace(local, **changes)  # type: ignore[arg-type]
    result = await BillingReconciliationClassifier().classify_difference(local=local, provider=provider)
    assert result is expected


@pytest.mark.asyncio
async def test_price_and_currency_mismatches_take_precedence_over_newer_provider_state() -> None:
    local = _snapshot()
    provider = replace(
        local, currency=CurrencyCode.USD, provider_price_reference="other", provider_updated_at=_NOW + timedelta(days=1)
    )
    result = await BillingReconciliationClassifier().classify_difference(local=local, provider=provider)
    assert result is BillingReconciliationDifferenceCode.CURRENCY_MISMATCH


@pytest.mark.asyncio
async def test_lost_simulator_state_is_unresolved_and_never_triggers_a_new_checkout() -> None:
    provider = SimulatedBillingProviderGateway(webhook_secret=b"synthetic-secret-for-reconciliation-test")
    inspection = BillingReconciliationInspection(provider, BillingReconciliationClassifier())

    result = await inspection.inspect(local=_snapshot())

    assert result is BillingReconciliationDifferenceCode.UNRESOLVED
    assert provider._idempotency == {}  # No checkout or refund was attempted.


@pytest.mark.asyncio
async def test_missing_local_mapping_is_not_looked_up() -> None:
    provider = SimulatedBillingProviderGateway(webhook_secret=b"synthetic-secret-for-reconciliation-test")
    inspection = BillingReconciliationInspection(provider, BillingReconciliationClassifier())

    result = await inspection.inspect(local=None)

    assert result is BillingReconciliationDifferenceCode.MAPPING_MISSING
    assert provider._idempotency == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("currency", list(CurrencyCode))
async def test_simulator_restart_without_durable_evidence_is_unresolved(currency: CurrencyCode) -> None:
    secret = b"synthetic-secret-for-reconciliation-test"
    provider = SimulatedBillingProviderGateway(webhook_secret=secret, clock=lambda: _NOW)
    command = BillingCheckoutCommand(uuid4(), uuid4(), currency, "sim_price_1", BillingReturnTarget.SUBSCRIPTION)
    checkout = await provider.create_checkout(command=command, idempotency_key="synthetic-checkout")
    classifier = BillingReconciliationClassifier()
    before_restart = await BillingReconciliationInspection(provider, classifier).inspect(local=checkout.subscription)

    restarted = SimulatedBillingProviderGateway(webhook_secret=secret, clock=lambda: _NOW)
    after_restart = await BillingReconciliationInspection(restarted, classifier).inspect(local=checkout.subscription)

    assert before_restart is BillingReconciliationDifferenceCode.IN_SYNC
    assert after_restart is BillingReconciliationDifferenceCode.UNRESOLVED
    assert restarted._idempotency == {}


@pytest.mark.asyncio
async def test_newer_simulated_payment_is_detected_without_changing_the_local_snapshot() -> None:
    now = _NOW
    provider = SimulatedBillingProviderGateway(
        webhook_secret=b"synthetic-secret-for-reconciliation-test", clock=lambda: now
    )
    command = BillingCheckoutCommand(
        uuid4(), uuid4(), CurrencyCode.CAD, "sim_price_1", BillingReturnTarget.SUBSCRIPTION
    )
    checkout = await provider.create_checkout(command=command, idempotency_key="synthetic-checkout")
    now += timedelta(seconds=1)
    provider.emit_webhook(
        checkout_reference=checkout.provider_checkout_reference, scenario=SimulatedWebhookScenario.INVOICE_PAID
    )

    result = await BillingReconciliationInspection(provider, BillingReconciliationClassifier()).inspect(
        local=checkout.subscription
    )

    assert result is BillingReconciliationDifferenceCode.LOCAL_STALE
    assert checkout.subscription.state is SubscriptionState.PENDING_CHECKOUT


@pytest.mark.asyncio
async def test_observation_preserves_scope_and_reports_a_version_conflict() -> None:
    class Repository:
        def __init__(self) -> None:
            self.recorded: tuple[ReconciliationCandidate, BillingReconciliationDifferenceCode] | None = None

        async def record_observation(
            self, *, candidate: ReconciliationCandidate, difference: BillingReconciliationDifferenceCode
        ) -> bool:
            self.recorded = (candidate, difference)
            return False  # The transaction detected that the local version changed.

    provider = SimulatedBillingProviderGateway(webhook_secret=b"synthetic-secret-for-reconciliation-test")
    repository = Repository()
    observer = BillingReconciliationObserver(
        BillingReconciliationInspection(provider, BillingReconciliationClassifier()), repository
    )
    candidate = ReconciliationCandidate(uuid4(), uuid4(), uuid4(), 1, _snapshot())

    assert not await observer.observe(candidate=candidate)
    assert repository.recorded == (candidate, BillingReconciliationDifferenceCode.UNRESOLVED)
    assert provider._idempotency == {}


@pytest.mark.parametrize(
    ("kind", "interval"),
    [
        (ReconciliationScheduleKind.INCREMENTAL, timedelta(minutes=15)),
        (ReconciliationScheduleKind.EXHAUSTIVE, timedelta(days=1)),
    ],
)
def test_schedule_replays_missed_closed_windows_one_at_a_time(
    kind: ReconciliationScheduleKind, interval: timedelta
) -> None:
    boundary = _NOW if kind is ReconciliationScheduleKind.INCREMENTAL else _NOW.replace(hour=0)
    first = next_reconciliation_window(kind=kind, now=_NOW, last_window_end=boundary - 2 * interval)
    assert first is not None
    assert (first.starts_at, first.ends_at) == (boundary - 2 * interval, boundary - interval)
    second = next_reconciliation_window(kind=kind, now=_NOW, last_window_end=first.ends_at)
    assert second is not None
    assert second.ends_at == boundary
    assert next_reconciliation_window(kind=kind, now=_NOW, last_window_end=second.ends_at) is None


def test_schedule_initial_window_and_invalid_checkpoints() -> None:
    first = next_reconciliation_window(kind=ReconciliationScheduleKind.INCREMENTAL, now=_NOW, last_window_end=None)
    assert first is not None
    assert (first.starts_at, first.ends_at) == (_NOW - timedelta(minutes=15), _NOW)
    with pytest.raises(ValueError):
        next_reconciliation_window(
            kind=ReconciliationScheduleKind.INCREMENTAL, now=datetime(2026, 10, 22), last_window_end=None
        )
    with pytest.raises(ValueError):
        next_reconciliation_window(
            kind=ReconciliationScheduleKind.INCREMENTAL, now=_NOW, last_window_end=_NOW - timedelta(minutes=1)
        )


@pytest.mark.asyncio
async def test_scheduler_reserves_only_the_next_missed_window() -> None:
    class Repository:
        def __init__(self) -> None:
            self.windows: list[ReconciliationWindow] = []
            self.run_id = uuid4()

        async def last_window_end(self, *, kind: ReconciliationScheduleKind) -> datetime:
            assert kind is ReconciliationScheduleKind.INCREMENTAL
            return _NOW - timedelta(minutes=30)

        async def schedule_window(self, *, window: ReconciliationWindow) -> UUID:
            self.windows.append(window)
            return self.run_id

    repository = Repository()
    scheduler = BillingReconciliationScheduler(repository)
    result = await scheduler.schedule_next(kind=ReconciliationScheduleKind.INCREMENTAL, now=_NOW)

    assert result == repository.run_id
    assert len(repository.windows) == 1
    assert repository.windows[0].starts_at == _NOW - timedelta(minutes=30)
    assert repository.windows[0].ends_at == _NOW - timedelta(minutes=15)


@pytest.mark.asyncio
@pytest.mark.parametrize("currency", list(CurrencyCode))
async def test_correction_candidate_requires_consistent_newer_simulated_payment_evidence(
    currency: CurrencyCode,
) -> None:
    local = _snapshot(currency)
    provider = replace(local, state=SubscriptionState.ACTIVE, provider_updated_at=_NOW + timedelta(seconds=1))
    event = NormalizedBillingEvent(
        BillingProvider.SIMULATED,
        "sim_event_1",
        BillingEventType.INVOICE_PAID,
        provider.provider_subscription_reference,
        provider.provider_updated_at,
        provider,
    )
    assert await is_reconciliation_correction_candidate(local=local, provider=provider, event=event)
    assert not await is_reconciliation_correction_candidate(
        local=local, provider=provider, event=replace(event, provider=BillingProvider.STRIPE)
    )
    assert not await is_reconciliation_correction_candidate(
        local=local, provider=provider, event=replace(event, provider_object_reference="other")
    )
    assert not await is_reconciliation_correction_candidate(
        local=local, provider=provider, event=replace(event, normalized_subscription=None)
    )
    assert not await is_reconciliation_correction_candidate(
        local=local,
        provider=replace(provider, currency=CurrencyCode.USD if currency is not CurrencyCode.USD else CurrencyCode.CAD),
        event=event,
    )
    assert not await is_reconciliation_correction_candidate(
        local=replace(local, state=SubscriptionState.CANCELED), provider=provider, event=event
    )
