"""Classification prudente des écarts Billing, sans effet sur les abonnements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from ...domain.billing import (
    BillingErrorCode,
    BillingEventType,
    BillingProvider,
    SubscriptionState,
    SubscriptionTransitionError,
    SubscriptionTransitionTrigger,
    next_subscription_state,
)
from ..errors import BillingOperationError
from ..ports.billing import (
    BillingReconciliationDifferenceCode,
    NormalizedBillingEvent,
    NormalizedSubscriptionSnapshot,
)
from ..ports.clock import Clock
from ..tenancy import ActorContext
from .billing import BillingSessionUseCases, _digest


class BillingReconciliationClassifier:
    """Compare deux instantanés sans supposer qu'une horloge égale ordonne les faits.

    Cette classe ne prouve pas l'identité d'un tenant, ne déclenche aucun paiement
    et ne modifie aucune projection. Une correction éventuelle doit revérifier ces
    conditions ainsi que les versions dans une transaction distincte et auditée.
    """

    async def classify_difference(
        self, *, local: NormalizedSubscriptionSnapshot, provider: NormalizedSubscriptionSnapshot
    ) -> BillingReconciliationDifferenceCode:
        code = BillingReconciliationDifferenceCode
        if (
            not local.provider_subscription_reference.strip()
            or not provider.provider_subscription_reference.strip()
            or not local.provider_customer_reference.strip()
            or not provider.provider_customer_reference.strip()
            or local.provider_subscription_reference != provider.provider_subscription_reference
            or local.provider_customer_reference != provider.provider_customer_reference
        ):
            return code.MAPPING_MISSING
        if local.currency != provider.currency:
            return code.CURRENCY_MISMATCH
        if not local.provider_price_reference.strip() or not provider.provider_price_reference.strip():
            return code.MAPPING_MISSING
        if local.provider_price_reference != provider.provider_price_reference:
            return code.PRICE_MISMATCH
        if local.provider_updated_at.utcoffset() is None or provider.provider_updated_at.utcoffset() is None:
            return code.UNRESOLVED

        local_projection = (local.state, local.period, local.cancel_at_period_end)
        provider_projection = (provider.state, provider.period, provider.cancel_at_period_end)
        if local_projection == provider_projection:
            return code.IN_SYNC
        if provider.provider_updated_at > local.provider_updated_at:
            return code.LOCAL_STALE
        if provider.provider_updated_at < local.provider_updated_at:
            return code.PROVIDER_STALE
        return code.UNRESOLVED


async def is_reconciliation_correction_candidate(
    *,
    local: NormalizedSubscriptionSnapshot,
    provider: NormalizedSubscriptionSnapshot,
    event: NormalizedBillingEvent,
) -> bool:
    """Vérifie les seules transitions simples potentiellement corrigeables.

    Ce résultat n'est pas une autorisation de mutation : la transaction devra
    encore prouver l'admission signée de l'événement et revérifier la version,
    l'organisation, les privilèges et l'audit avant tout effet.
    """

    if (
        await BillingReconciliationClassifier().classify_difference(local=local, provider=provider)
        is not BillingReconciliationDifferenceCode.LOCAL_STALE
    ):
        return False
    if (
        event.provider is not BillingProvider.SIMULATED
        or not event.provider_event_id.strip()
        or event.provider_object_reference != provider.provider_subscription_reference
        or event.normalized_subscription != provider
        or event.provider_created_at.utcoffset() is None
        or event.provider_created_at != provider.provider_updated_at
        or local.cancel_at_period_end != provider.cancel_at_period_end
        or provider.period.starts_at < local.period.starts_at
        or provider.period.ends_at < local.period.ends_at
    ):
        return False
    if event.event_type is BillingEventType.INVOICE_PAID and provider.state is SubscriptionState.ACTIVE:
        trigger = SubscriptionTransitionTrigger.INVOICE_PAID
    elif event.event_type is BillingEventType.INVOICE_PAYMENT_FAILED and provider.state is SubscriptionState.PAST_DUE:
        trigger = SubscriptionTransitionTrigger.PAYMENT_FAILED
    else:
        return False
    if local.state is provider.state:
        return True
    try:
        return next_subscription_state(local.state, trigger) is provider.state
    except SubscriptionTransitionError:
        return False


class BillingSubscriptionSnapshotReader(Protocol):
    async def get_subscription(self, *, provider_subscription_reference: str) -> NormalizedSubscriptionSnapshot: ...


class BillingReconciliationInspection:
    """Relit un instantané existant, sans créer de checkout ou de remboursement."""

    def __init__(
        self, provider: BillingSubscriptionSnapshotReader, classifier: BillingReconciliationClassifier
    ) -> None:
        self._provider = provider
        self._classifier = classifier

    async def inspect(self, *, local: NormalizedSubscriptionSnapshot | None) -> BillingReconciliationDifferenceCode:
        if local is None or not local.provider_subscription_reference.strip():
            return BillingReconciliationDifferenceCode.MAPPING_MISSING
        try:
            remote = await self._provider.get_subscription(
                provider_subscription_reference=local.provider_subscription_reference
            )
        except TimeoutError:
            return BillingReconciliationDifferenceCode.UNRESOLVED
        except BillingOperationError as error:
            if error.code in {
                BillingErrorCode.PROVIDER_DISABLED,
                BillingErrorCode.PROVIDER_UNAVAILABLE,
                BillingErrorCode.STATE_UNKNOWN,
                BillingErrorCode.RECONCILIATION_REQUIRED,
            }:
                return BillingReconciliationDifferenceCode.UNRESOLVED
            raise
        return await self._classifier.classify_difference(local=local, provider=remote)


@dataclass(frozen=True, slots=True)
class ReconciliationCandidate:
    """Instantané local lu pour un abonnement et une exécution explicitement identifiés."""

    run_id: UUID
    organization_id: UUID
    subscription_id: UUID
    local_version: int
    snapshot: NormalizedSubscriptionSnapshot

    def __post_init__(self) -> None:
        if self.local_version < 1:
            raise ValueError("La version de l'abonnement doit être positive.")


class BillingReconciliationObservationRepository(Protocol):
    async def record_observation(
        self, *, candidate: ReconciliationCandidate, difference: BillingReconciliationDifferenceCode
    ) -> bool:
        """Enregistrer atomiquement l'écart si la version et la portée sont encore valides.

        False désigne un conflit ou une perte de la réservation. Aucun appel à
        ce contrat n'autorise à modifier l'abonnement ou une commande financière.
        """
        ...


class BillingReconciliationObserver:
    """Inspection sans effet financier suivie d'une observation conditionnelle."""

    def __init__(
        self, inspection: BillingReconciliationInspection, repository: BillingReconciliationObservationRepository
    ) -> None:
        self._inspection = inspection
        self._repository = repository

    async def observe(self, *, candidate: ReconciliationCandidate) -> bool:
        difference = await self._inspection.inspect(local=candidate.snapshot)
        return await self._repository.record_observation(candidate=candidate, difference=difference)


@dataclass(frozen=True, slots=True)
class ReconciliationLease:
    """Réservation opaque d'une exécution ; son contrôle effectif appartient à la base."""

    run_id: UUID
    token: UUID
    organization_id: UUID | None


class ReconciliationReadStatus(StrEnum):
    CANDIDATE = "candidate"
    EXHAUSTED = "exhausted"
    LEASE_LOST = "lease_lost"


@dataclass(frozen=True, slots=True)
class ReconciliationRead:
    status: ReconciliationReadStatus
    candidate: ReconciliationCandidate | None = None

    def __post_init__(self) -> None:
        if (self.status is ReconciliationReadStatus.CANDIDATE) != (self.candidate is not None):
            raise ValueError("La lecture doit contenir exactement le candidat annoncé.")


class BillingReconciliationRunRepository(Protocol):
    """Contrat de reprise : les vérifications et mutations sont atomiques en base."""

    async def read_next(self, *, lease: ReconciliationLease) -> ReconciliationRead:
        """Relire la réservation et le prochain abonnement ; distinguer fin et perte du bail."""
        ...

    async def record_and_advance(
        self,
        *,
        lease: ReconciliationLease,
        candidate: ReconciliationCandidate,
        difference: BillingReconciliationDifferenceCode,
    ) -> bool:
        """Vérifier bail et version, puis enregistrer observation, audit et curseur ensemble."""
        ...

    async def complete(self, *, lease: ReconciliationLease) -> bool:
        """Terminer seulement si le bail est valide et la sélection réellement épuisée."""
        ...


class ReconciliationRunResult(StrEnum):
    COMPLETED = "completed"
    YIELDED = "yielded"
    LEASE_OR_VERSION_CONFLICT = "lease_or_version_conflict"


class BillingReconciliationRunProcessor:
    """Traite un lot borné ; toute correction reste gardée par PostgreSQL."""

    def __init__(
        self,
        *,
        provider: BillingProvider,
        inspection: BillingReconciliationInspection,
        repository: BillingReconciliationRunRepository,
    ) -> None:
        if provider is not BillingProvider.SIMULATED:
            raise ValueError("La réconciliation P53-08 est réservée au simulateur.")
        self._inspection = inspection
        self._repository = repository

    async def process(self, *, lease: ReconciliationLease, batch_size: int = 100) -> ReconciliationRunResult:
        if not 1 <= batch_size <= 100:
            raise ValueError("La taille du lot doit être comprise entre 1 et 100.")
        for _ in range(batch_size):
            read = await self._repository.read_next(lease=lease)
            if read.status is ReconciliationReadStatus.LEASE_LOST:
                return ReconciliationRunResult.LEASE_OR_VERSION_CONFLICT
            if read.status is ReconciliationReadStatus.EXHAUSTED:
                if await self._repository.complete(lease=lease):
                    return ReconciliationRunResult.COMPLETED
                return ReconciliationRunResult.LEASE_OR_VERSION_CONFLICT
            candidate = read.candidate
            if candidate is None or candidate.run_id != lease.run_id:
                raise ValueError("Le candidat n'appartient pas à cette exécution.")
            if lease.organization_id is not None and candidate.organization_id != lease.organization_id:
                raise ValueError("Le candidat n'appartient pas à l'organisation demandée.")
            difference = await self._inspection.inspect(local=candidate.snapshot)
            if not await self._repository.record_and_advance(lease=lease, candidate=candidate, difference=difference):
                return ReconciliationRunResult.LEASE_OR_VERSION_CONFLICT
        return ReconciliationRunResult.YIELDED


class BillingReconciliationLeaseRepository(Protocol):
    async def claim(self) -> ReconciliationLease | None: ...

    async def release(self, *, lease: ReconciliationLease) -> bool: ...


class BillingReconciliationWorker:
    """Un lot borné ; une panne laisse expirer le bail sans inventer de résultat."""

    def __init__(
        self, *, leases: BillingReconciliationLeaseRepository, processor: BillingReconciliationRunProcessor
    ) -> None:
        self._leases = leases
        self._processor = processor

    async def run_once(self) -> bool:
        lease = await self._leases.claim()
        if lease is None:
            return False
        result = await self._processor.process(lease=lease)
        if result is not ReconciliationRunResult.COMPLETED:
            # L'échec de libération signifie que le bail a déjà été perdu ; on
            # n'essaie jamais de modifier une réservation détenue par un autre worker.
            await self._leases.release(lease=lease)
        return True


class ReconciliationReason(StrEnum):
    PAYMENT_UNCERTAIN = "payment_uncertain"
    STATE_MISMATCH = "state_mismatch"
    OPERATOR_REVIEW = "operator_review"


class BillingManualReconciliationRepository(Protocol):
    async def request(
        self, *, context: ActorContext, organization_id: UUID, reason: ReconciliationReason, key_digest: str
    ) -> UUID: ...


class BillingManualReconciliation:
    """Demande plateforme ciblée, sans action financière et sans texte libre sensible."""

    def __init__(self, repository: BillingManualReconciliationRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def request(
        self,
        *,
        context: ActorContext,
        organization_id: UUID,
        reason: ReconciliationReason,
        idempotency_key: str,
        authorized: bool,
        session_issued_at: datetime | None,
    ) -> UUID:
        BillingSessionUseCases._require_recent_authorization(authorized, session_issued_at, self._clock.now())
        if not isinstance(reason, ReconciliationReason):
            raise ValueError("Le motif de réconciliation est invalide.")
        return await self._repository.request(
            context=context, organization_id=organization_id, reason=reason, key_digest=_digest(idempotency_key)
        )


class ReconciliationScheduleKind(StrEnum):
    INCREMENTAL = "incremental"
    EXHAUSTIVE = "exhaustive"


@dataclass(frozen=True, slots=True)
class ReconciliationWindow:
    kind: ReconciliationScheduleKind
    starts_at: datetime
    ends_at: datetime


def next_reconciliation_window(
    *, kind: ReconciliationScheduleKind, now: datetime, last_window_end: datetime | None
) -> ReconciliationWindow | None:
    """Propose au plus une fenêtre fermée ; la déduplication est à faire en base.

    La reprise démarre à la dernière borne persistée, sans sauter les fenêtres
    manquées. Sur une première exécution, seule la dernière fenêtre fermée est
    proposée. La persistance atomique et l'ordonnancement restent à raccorder.
    """

    if now.utcoffset() is None or (last_window_end is not None and last_window_end.utcoffset() is None):
        raise ValueError("Les horodatages de réconciliation doivent être explicites.")
    interval = {
        ReconciliationScheduleKind.INCREMENTAL: timedelta(minutes=15),
        ReconciliationScheduleKind.EXHAUSTIVE: timedelta(days=1),
    }[kind]
    instant = now.astimezone(UTC)
    epoch = datetime(2000, 1, 1, tzinfo=UTC)
    boundary = epoch + ((instant - epoch) // interval) * interval
    if last_window_end is None:
        starts_at = boundary - interval
    else:
        starts_at = last_window_end.astimezone(UTC)
        if (starts_at - epoch) % interval != timedelta(0):
            raise ValueError("La dernière borne de réconciliation n'est pas alignée.")
    ends_at = starts_at + interval
    if ends_at > boundary:
        return None
    return ReconciliationWindow(kind, starts_at, ends_at)


class BillingReconciliationScheduleRepository(Protocol):
    async def last_window_end(self, *, kind: ReconciliationScheduleKind) -> datetime | None: ...

    async def schedule_window(self, *, window: ReconciliationWindow) -> UUID | None: ...


class BillingReconciliationScheduler:
    """Prépare une fenêtre au plus ; l'insertion en base reste la source d'idempotence."""

    def __init__(self, repository: BillingReconciliationScheduleRepository) -> None:
        self._repository = repository

    async def schedule_next(self, *, kind: ReconciliationScheduleKind, now: datetime) -> UUID | None:
        last_end = await self._repository.last_window_end(kind=kind)
        window = next_reconciliation_window(kind=kind, now=now, last_window_end=last_end)
        return None if window is None else await self._repository.schedule_window(window=window)
