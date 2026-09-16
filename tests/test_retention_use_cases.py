from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from backend.app.application.errors import AcquisitionNotApproved, IdempotencyKeyReused, InsufficientCapability
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases import (
    ArchiveProspectUseCase,
    DeclareImportUseCase,
    PlaceRetentionHoldUseCase,
    ReleaseRetentionHoldUseCase,
)
from backend.app.domain.prospect import (
    AcquisitionRecordView,
    AcquisitionStatus,
    ArchiveReasonCode,
    ImportDeclarationDraft,
    ImportDeclarationStatus,
    ImportDeclarationView,
    ProspectOrigin,
    ProspectStageCode,
    ProspectView,
    ProvenanceSourceKind,
    RetentionHoldDraft,
    RetentionHoldReasonCode,
    RetentionHoldReleaseReasonCode,
    RetentionHoldView,
    RetentionResourceType,
)

NOW = datetime(2026, 8, 14, 18, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class MemoryAuditRecorder:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def record(self, event: object) -> UUID:
        self.events.append(event)
        return uuid4()


class MemoryAcquisitions:
    def __init__(self, context: TenantContext) -> None:
        self.approved = AcquisitionRecordView(
            id=uuid4(),
            organization_id=context.organization_id,
            source_kind=ProvenanceSourceKind.CSV,
            source_label="CSV client",
            provider_id=uuid4(),
            purpose="commercial_follow_up",
            territory="CA-QC",
            obtained_at=NOW - timedelta(days=1),
            declared_by=context.actor_id,
            data_categories=("business_identity", "person_identity", "email"),
            status=AcquisitionStatus.APPROVED,
            decision_reason_code=None,
            external_reference=None,
            version=1,
            created_at=NOW,
            updated_at=NOW,
            decided_at=NOW,
            decided_by=context.actor_id,
            command_fingerprint=None,
        )
        self.quarantined = replace(self.approved, id=uuid4(), status=AcquisitionStatus.QUARANTINED)

    async def get(self, acquisition_id: UUID) -> AcquisitionRecordView | None:
        if acquisition_id == self.approved.id:
            return self.approved
        if acquisition_id == self.quarantined.id:
            return self.quarantined
        return None


class MemoryImportDeclarations:
    def __init__(self) -> None:
        self.items: dict[UUID, ImportDeclarationView] = {}
        self.by_key: dict[str, ImportDeclarationView] = {}

    async def add(
        self,
        draft: ImportDeclarationDraft,
        *,
        now: datetime,
        status: str,
        decision_reason_codes: tuple[str, ...],
    ) -> ImportDeclarationView:
        view = ImportDeclarationView(
            id=uuid4(),
            organization_id=draft.organization_id,
            acquisition_record_id=draft.acquisition_record_id,
            declaration_label=draft.declaration_label,
            format_code=draft.format_code,
            schema_code=draft.schema_code,
            declared_field_codes=draft.declared_field_codes,
            declared_data_categories=draft.declared_data_categories,
            estimated_row_count=draft.estimated_row_count,
            declared_content_sha256=draft.declared_content_sha256,
            status=ImportDeclarationStatus(status),
            decision_reason_codes=decision_reason_codes,
            declared_by=draft.declared_by,
            declared_at=now,
            cancelled_at=None,
            archived_at=None,
            archived_by=None,
            archive_reason_code=None,
            version=1,
            created_at=now,
            updated_at=now,
            command_fingerprint=draft.command_fingerprint,
        )
        self.items[view.id] = view
        if draft.idempotency_key:
            self.by_key[draft.idempotency_key] = view
        return view

    async def get_by_idempotency_key(self, idempotency_key: str) -> ImportDeclarationView | None:
        return self.by_key.get(idempotency_key)


class MemoryRetentionHolds:
    def __init__(self) -> None:
        self.items: dict[UUID, RetentionHoldView] = {}
        self.by_key: dict[str, RetentionHoldView] = {}

    async def add(self, draft: RetentionHoldDraft, *, now: datetime) -> RetentionHoldView:
        view = RetentionHoldView(
            id=uuid4(),
            organization_id=draft.organization_id,
            resource_type=draft.resource_type,
            resource_id=draft.resource_id,
            reason_code=draft.reason_code,
            note=draft.note,
            placed_at=now,
            placed_by=draft.placed_by,
            released_at=None,
            released_by=None,
            release_reason_code=None,
            version=1,
            created_at=now,
            updated_at=now,
            command_fingerprint=draft.command_fingerprint,
        )
        self.items[view.id] = view
        if draft.idempotency_key:
            self.by_key[draft.idempotency_key] = view
        return view

    async def get(self, hold_id: UUID) -> RetentionHoldView | None:
        return self.items.get(hold_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> RetentionHoldView | None:
        return self.by_key.get(idempotency_key)

    async def release(
        self,
        hold_id: UUID,
        *,
        expected_version: int,
        release_reason_code: RetentionHoldReleaseReasonCode,
        released_by: UUID,
        now: datetime,
    ) -> RetentionHoldView | None:
        hold = self.items.get(hold_id)
        if hold is None or hold.version != expected_version or hold.released_at is not None:
            return None
        updated = replace(
            hold,
            released_at=now,
            released_by=released_by,
            release_reason_code=release_reason_code,
            version=hold.version + 1,
            updated_at=now,
        )
        self.items[hold_id] = updated
        return updated


class MemoryProspects:
    def __init__(self, context: TenantContext) -> None:
        self.item = ProspectView(
            id=uuid4(),
            organization_id=context.organization_id,
            internal_alias="Entreprise QA",
            origin=ProspectOrigin.MANUAL,
            source_label="manual:user_entry",
            google_place_id=None,
            stage_code=ProspectStageCode.NEW,
            priority=0,
            version=2,
            created_at=NOW,
            updated_at=NOW,
            archived_at=None,
        )

    async def get(self, prospect_id: UUID) -> ProspectView | None:
        return self.item if prospect_id == self.item.id else None

    async def archive_with_cascade(
        self, prospect_id: UUID, *, expected_version: int, now: datetime, reason_code: str = "other"
    ) -> tuple[ProspectView, int, int] | None:
        del reason_code
        if prospect_id != self.item.id or expected_version != self.item.version:
            return None
        self.item = replace(
            self.item,
            stage_code=ProspectStageCode.ARCHIVED,
            version=self.item.version + 1,
            archived_at=now,
            updated_at=now,
        )
        return self.item, 2, 3


@dataclass(slots=True)
class MemoryRetentionUnitOfWork:
    acquisitions: MemoryAcquisitions
    import_declarations: MemoryImportDeclarations
    retention_holds: MemoryRetentionHolds
    prospects: MemoryProspects
    audit: MemoryAuditRecorder
    committed: bool = False

    async def __aenter__(self) -> MemoryRetentionUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False


@pytest.fixture
def context() -> TenantContext:
    return TenantContext(actor_id=uuid4(), organization_id=uuid4(), request_id="retention-use-case")


@pytest.fixture
def unit_of_work(context: TenantContext) -> MemoryRetentionUnitOfWork:
    return MemoryRetentionUnitOfWork(
        acquisitions=MemoryAcquisitions(context),
        import_declarations=MemoryImportDeclarations(),
        retention_holds=MemoryRetentionHolds(),
        prospects=MemoryProspects(context),
        audit=MemoryAuditRecorder(),
    )


@pytest.mark.asyncio
async def test_declare_import_records_metadata_only_and_is_idempotent(
    context: TenantContext, unit_of_work: MemoryRetentionUnitOfWork
) -> None:
    use_case = DeclareImportUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    first = await use_case.execute(
        context=context,
        has_capability=True,
        acquisition_record_id=unit_of_work.acquisitions.approved.id,
        declaration_label="Lot Quebec aout",
        format_code="csv",
        schema_code="prospect_contacts_v1",
        declared_field_codes=("business_name", "email"),
        declared_data_categories=("business_identity", "email"),
        estimated_row_count=42,
        declared_content_sha256=None,
        idempotency_key="import-key",
    )
    replay = await use_case.execute(
        context=context,
        has_capability=True,
        acquisition_record_id=unit_of_work.acquisitions.approved.id,
        declaration_label="Lot Quebec aout",
        format_code="csv",
        schema_code="prospect_contacts_v1",
        declared_field_codes=("business_name", "email"),
        declared_data_categories=("business_identity", "email"),
        estimated_row_count=42,
        declared_content_sha256=None,
        idempotency_key="import-key",
    )

    assert first.status is ImportDeclarationStatus.DECLARED
    assert first.declared_field_codes == ("business_name", "email")
    assert first.id == replay.id
    assert len(unit_of_work.audit.events) == 1
    assert unit_of_work.committed is True


@pytest.mark.asyncio
async def test_declare_import_quarantines_high_risk_notes_without_storing_rows(
    context: TenantContext, unit_of_work: MemoryRetentionUnitOfWork
) -> None:
    use_case = DeclareImportUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    declaration = await use_case.execute(
        context=context,
        has_capability=True,
        acquisition_record_id=unit_of_work.acquisitions.approved.id,
        declaration_label="Lot avec notes",
        format_code="csv",
        schema_code="prospect_contacts_v1",
        declared_field_codes=("business_name", "notes"),
        declared_data_categories=("business_identity", "person_identity"),
        estimated_row_count=None,
        declared_content_sha256=None,
        idempotency_key="notes-key",
    )

    assert declaration.status is ImportDeclarationStatus.QUARANTINED
    assert declaration.decision_reason_codes == ("high_risk_free_text",)


@pytest.mark.asyncio
async def test_import_requires_approved_acquisition(
    context: TenantContext, unit_of_work: MemoryRetentionUnitOfWork
) -> None:
    use_case = DeclareImportUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    with pytest.raises(AcquisitionNotApproved):
        await use_case.execute(
            context=context,
            has_capability=True,
            acquisition_record_id=unit_of_work.acquisitions.quarantined.id,
            declaration_label="Lot refuse",
            format_code="csv",
            schema_code="prospect_contacts_v1",
            declared_field_codes=("business_name",),
            declared_data_categories=("business_identity",),
            estimated_row_count=None,
            declared_content_sha256=None,
            idempotency_key="bad-acquisition",
        )


@pytest.mark.asyncio
async def test_retention_hold_is_idempotent_and_release_is_audited(
    context: TenantContext, unit_of_work: MemoryRetentionUnitOfWork
) -> None:
    place = PlaceRetentionHoldUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]
    release = ReleaseRetentionHoldUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]
    resource_id = uuid4()

    hold = await place.execute(
        context=context,
        has_capability=True,
        resource_type=RetentionResourceType.PROSPECT,
        resource_id=resource_id,
        reason_code=RetentionHoldReasonCode.QUALITY_REVIEW,
        note=None,
        idempotency_key="hold-key",
    )
    replay = await place.execute(
        context=context,
        has_capability=True,
        resource_type=RetentionResourceType.PROSPECT,
        resource_id=resource_id,
        reason_code=RetentionHoldReasonCode.QUALITY_REVIEW,
        note=None,
        idempotency_key="hold-key",
    )
    released = await release.execute(
        context=context,
        has_capability=True,
        hold_id=hold.id,
        expected_version=hold.version,
        release_reason_code=RetentionHoldReleaseReasonCode.RESOLVED,
    )

    assert replay.id == hold.id
    assert released.released_by == context.actor_id
    assert len(unit_of_work.audit.events) == 2


@pytest.mark.asyncio
async def test_idempotency_key_with_different_hold_body_is_rejected(
    context: TenantContext, unit_of_work: MemoryRetentionUnitOfWork
) -> None:
    use_case = PlaceRetentionHoldUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    await use_case.execute(
        context=context,
        has_capability=True,
        resource_type=RetentionResourceType.PROSPECT,
        resource_id=uuid4(),
        reason_code=RetentionHoldReasonCode.QUALITY_REVIEW,
        note=None,
        idempotency_key="hold-key",
    )
    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute(
            context=context,
            has_capability=True,
            resource_type=RetentionResourceType.CONTACT,
            resource_id=uuid4(),
            reason_code=RetentionHoldReasonCode.QUALITY_REVIEW,
            note=None,
            idempotency_key="hold-key",
        )


@pytest.mark.asyncio
async def test_archive_prospect_cascades_and_requires_capability(
    context: TenantContext, unit_of_work: MemoryRetentionUnitOfWork
) -> None:
    use_case = ArchiveProspectUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    with pytest.raises(InsufficientCapability):
        await use_case.execute(
            context=context,
            has_capability=False,
            prospect_id=unit_of_work.prospects.item.id,
            expected_version=unit_of_work.prospects.item.version,
            archive_reason_code=ArchiveReasonCode.NO_LONGER_RELEVANT,
        )

    outcome = await use_case.execute(
        context=context,
        has_capability=True,
        prospect_id=unit_of_work.prospects.item.id,
        expected_version=unit_of_work.prospects.item.version,
        archive_reason_code=ArchiveReasonCode.NO_LONGER_RELEVANT,
    )

    assert outcome.contacts_archived == 2
    assert outcome.channels_archived == 3
    assert len(unit_of_work.audit.events) == 1
