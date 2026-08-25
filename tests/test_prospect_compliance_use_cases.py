from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from backend.app.application.errors import IdempotencyKeyReused, InsufficientCapability
from backend.app.application.tenancy import TenantContext
from backend.app.application.use_cases import (
    ChangeContactPermissionUseCase,
    CreateContactChannelUseCase,
    DeclareAcquisitionUseCase,
    ManualSourceCommand,
)
from backend.app.domain.prospect import (
    AcquisitionDraft,
    AcquisitionRecordView,
    AcquisitionStatus,
    ContactChannelDraft,
    ContactChannelType,
    ContactChannelView,
    ContactDraft,
    ContactPermissionStatus,
    ContactPermissionView,
    ContactView,
    ProspectDraft,
    ProspectOrigin,
    ProspectStageCode,
    ProspectView,
    ProvenanceDraft,
    ProvenanceSourceKind,
    ProvenanceView,
    SourceProviderStatus,
    SourceProviderView,
)

NOW = datetime(2026, 8, 14, 16, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class MemoryAuditRecorder:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def record(self, event: object) -> UUID:
        self.events.append(event)
        return uuid4()


class MemoryProspects:
    def __init__(self, organization_id: UUID) -> None:
        self.item = ProspectView(
            id=uuid4(),
            organization_id=organization_id,
            internal_alias="Entreprise QA",
            origin=ProspectOrigin.MANUAL,
            source_label="manual:user_entry",
            google_place_id=None,
            stage_code=ProspectStageCode.NEW,
            priority=0,
            version=1,
            created_at=NOW,
            updated_at=NOW,
            archived_at=None,
        )

    async def add(self, draft: ProspectDraft, *, now: datetime) -> ProspectView:
        raise NotImplementedError

    async def get(self, prospect_id: UUID) -> ProspectView | None:
        return self.item if prospect_id == self.item.id else None

    async def get_by_google_place_id(self, google_place_id: str) -> ProspectView | None:
        return None

    async def list_active(
        self,
        *,
        limit: int,
        after_created_at: datetime | None = None,
        after_id: UUID | None = None,
        offset: int = 0,
    ) -> tuple[ProspectView, ...]:
        return (self.item,)

    async def archive(self, prospect_id: UUID, *, expected_version: int, now: datetime) -> ProspectView | None:
        return None


class MemoryProviders:
    def __init__(self, organization_id: UUID) -> None:
        self.provider = SourceProviderView(
            id=uuid4(),
            organization_id=organization_id,
            source_kind=ProvenanceSourceKind.CSV,
            label="CSV client",
            status=SourceProviderStatus.ACTIVE,
            terms_reference="DPA-2026",
            terms_url="https://example.ca/terms",
            valid_from=NOW - timedelta(days=1),
            valid_until=NOW + timedelta(days=30),
            allowed_territories=("CA-QC",),
            allowed_purposes=("commercial_follow_up",),
            allowed_data_categories=("business_identity", "email"),
            rights_attested_at=NOW,
            rights_attested_by=uuid4(),
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )

    async def get(self, provider_id: UUID) -> SourceProviderView | None:
        return self.provider if provider_id == self.provider.id else None


class MemoryAcquisitions:
    def __init__(self, providers: MemoryProviders, actor_id: UUID, organization_id: UUID) -> None:
        self.providers = providers
        self.actor_id = actor_id
        self.organization_id = organization_id
        self.items: dict[UUID, AcquisitionRecordView] = {}
        self.by_key: dict[str, AcquisitionRecordView] = {}

    async def add(
        self,
        draft: AcquisitionDraft,
        *,
        now: datetime,
        status: str,
        decision_reason_code: str | None = None,
        decided_by: UUID | None = None,
    ) -> AcquisitionRecordView:
        view = AcquisitionRecordView(
            id=uuid4(),
            organization_id=draft.organization_id,
            source_kind=draft.source_kind,
            source_label=draft.source_label,
            provider_id=draft.provider_id,
            purpose=draft.purpose,
            territory=draft.territory,
            obtained_at=draft.obtained_at,
            declared_by=draft.declared_by,
            data_categories=draft.data_categories,
            status=AcquisitionStatus(status),
            decision_reason_code=decision_reason_code,
            external_reference=draft.external_reference,
            version=1,
            created_at=now,
            updated_at=now,
            decided_at=now if decided_by else None,
            decided_by=decided_by,
            command_fingerprint=draft.command_fingerprint,
        )
        self.items[view.id] = view
        if draft.idempotency_key:
            self.by_key[draft.idempotency_key] = view
        return view

    async def get(self, acquisition_id: UUID) -> AcquisitionRecordView | None:
        return self.items.get(acquisition_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> AcquisitionRecordView | None:
        return self.by_key.get(idempotency_key)


class MemoryProvenance:
    def __init__(self) -> None:
        self.items: dict[UUID, ProvenanceView] = {}

    async def add(self, draft: ProvenanceDraft, *, now: datetime) -> ProvenanceView:
        view = ProvenanceView(
            id=uuid4(),
            organization_id=draft.organization_id,
            source_kind=draft.source_kind,
            source_label=draft.source_label,
            purpose=draft.purpose,
            obtained_at=draft.obtained_at,
            created_at=now,
            provider_id=draft.provider_id,
            acquisition_record_id=draft.acquisition_record_id,
        )
        self.items[view.id] = view
        return view

    async def get(self, provenance_id: UUID) -> ProvenanceView | None:
        return self.items.get(provenance_id)


class MemoryContacts:
    async def add(self, draft: ContactDraft, *, now: datetime) -> ContactView:
        raise NotImplementedError

    async def get(self, contact_id: UUID) -> ContactView | None:
        return None

    async def list_for_prospect(self, prospect_id: UUID) -> tuple[ContactView, ...]:
        return ()


class MemoryChannels:
    def __init__(self) -> None:
        self.items: dict[UUID, ContactChannelView] = {}

    async def add(self, draft: ContactChannelDraft, *, now: datetime) -> ContactChannelView:
        view = ContactChannelView(
            id=uuid4(),
            organization_id=draft.organization_id,
            channel_type=draft.channel_type,
            value=draft.value,
            value_normalized=draft.value_normalized,
            provenance_id=draft.provenance_id,
            prospect_id=draft.prospect_id,
            contact_id=draft.contact_id,
            purpose=draft.purpose,
            version=1,
            archived_at=None,
        )
        self.items[view.id] = view
        return view

    async def get(self, channel_id: UUID) -> ContactChannelView | None:
        return self.items.get(channel_id)

    async def find_by_normalized_value(
        self,
        *,
        channel_type: str,
        value_normalized: str,
    ) -> tuple[ContactChannelView, ...]:
        return tuple(
            item
            for item in self.items.values()
            if item.channel_type.value == channel_type and item.value_normalized == value_normalized
        )

    async def find_duplicate(
        self,
        *,
        channel_type: str,
        value_normalized: str,
        prospect_id: UUID | None,
        contact_id: UUID | None,
    ) -> ContactChannelView | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.channel_type.value == channel_type
                and item.value_normalized == value_normalized
                and item.prospect_id == prospect_id
                and item.contact_id == contact_id
            ),
            None,
        )


class MemoryPermissions:
    def __init__(self) -> None:
        self.items: dict[UUID, ContactPermissionView] = {}
        self.propagated = 0

    async def add_unknown(self, channel_id: UUID, *, organization_id: UUID, now: datetime) -> ContactPermissionView:
        permission = ContactPermissionView(
            id=uuid4(),
            organization_id=organization_id,
            channel_id=channel_id,
            status=ContactPermissionStatus.UNKNOWN,
            legal_basis_code=None,
            provenance_id=None,
            reason=None,
            decided_at=None,
            decided_by=None,
            valid_from=None,
            valid_until=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self.items[channel_id] = permission
        return permission

    async def get_by_channel(self, channel_id: UUID) -> ContactPermissionView | None:
        return self.items.get(channel_id)

    async def update(
        self,
        permission_id: UUID,
        *,
        expected_version: int,
        status: ContactPermissionStatus,
        now: datetime,
        decided_by: UUID,
        legal_basis_code: str | None = None,
        provenance_id: UUID | None = None,
        reason: str | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> ContactPermissionView | None:
        for channel_id, item in self.items.items():
            if item.id == permission_id and item.version == expected_version:
                updated = replace(item, status=status, decided_by=decided_by, version=item.version + 1)
                self.items[channel_id] = updated
                return updated
        return None

    async def apply_restriction_to_value(
        self,
        *,
        channel_type: str,
        value_normalized: str,
        status: ContactPermissionStatus,
        now: datetime,
        decided_by: UUID,
        reason: str | None,
    ) -> int:
        self.propagated += 1
        return self.propagated


@dataclass(slots=True)
class MemoryUnitOfWork:
    prospects: MemoryProspects
    source_providers: MemoryProviders
    acquisitions: MemoryAcquisitions
    provenance: MemoryProvenance
    contacts: MemoryContacts
    contact_channels: MemoryChannels
    contact_permissions: MemoryPermissions
    audit: MemoryAuditRecorder
    committed: bool = False

    async def __aenter__(self) -> MemoryUnitOfWork:
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
    return TenantContext(actor_id=uuid4(), organization_id=uuid4(), request_id="prospect-compliance")


@pytest.fixture
def unit_of_work(context: TenantContext) -> MemoryUnitOfWork:
    providers = MemoryProviders(context.organization_id)
    return MemoryUnitOfWork(
        prospects=MemoryProspects(context.organization_id),
        source_providers=providers,
        acquisitions=MemoryAcquisitions(providers, context.actor_id, context.organization_id),
        provenance=MemoryProvenance(),
        contacts=MemoryContacts(),
        contact_channels=MemoryChannels(),
        contact_permissions=MemoryPermissions(),
        audit=MemoryAuditRecorder(),
    )


@pytest.mark.asyncio
async def test_declare_acquisition_approves_matching_provider_and_is_idempotent(
    context: TenantContext,
    unit_of_work: MemoryUnitOfWork,
) -> None:
    use_case = DeclareAcquisitionUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    first = await use_case.execute(
        context=context,
        has_capability=True,
        source_kind=ProvenanceSourceKind.CSV,
        source_label="CSV client",
        provider_id=unit_of_work.source_providers.provider.id,
        purpose="commercial_follow_up",
        territory="CA-QC",
        obtained_at=NOW,
        data_categories=("business_identity", "email"),
        external_reference="batch-1",
        idempotency_key="same-key",
    )
    replay = await use_case.execute(
        context=context,
        has_capability=True,
        source_kind=ProvenanceSourceKind.CSV,
        source_label="CSV client",
        provider_id=unit_of_work.source_providers.provider.id,
        purpose="commercial_follow_up",
        territory="CA-QC",
        obtained_at=NOW,
        data_categories=("business_identity", "email"),
        external_reference="batch-1",
        idempotency_key="same-key",
    )

    assert first.status is AcquisitionStatus.APPROVED
    assert replay.id == first.id
    assert unit_of_work.committed is True
    assert len(unit_of_work.audit.events) == 1


@pytest.mark.asyncio
async def test_declare_acquisition_quarantines_contract_mismatch(
    context: TenantContext,
    unit_of_work: MemoryUnitOfWork,
) -> None:
    use_case = DeclareAcquisitionUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    acquisition = await use_case.execute(
        context=context,
        has_capability=True,
        source_kind=ProvenanceSourceKind.CSV,
        source_label="CSV client",
        provider_id=unit_of_work.source_providers.provider.id,
        purpose="commercial_follow_up",
        territory="US-NY",
        obtained_at=NOW,
        data_categories=("business_identity", "email"),
        external_reference=None,
        idempotency_key=None,
    )

    assert acquisition.status is AcquisitionStatus.QUARANTINED
    assert acquisition.decision_reason_code == "territory_not_allowed"
    assert len(unit_of_work.audit.events) == 2


@pytest.mark.asyncio
async def test_reused_idempotency_key_with_different_body_is_rejected(
    context: TenantContext,
    unit_of_work: MemoryUnitOfWork,
) -> None:
    use_case = DeclareAcquisitionUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]
    common = {
        "context": context,
        "has_capability": True,
        "source_kind": ProvenanceSourceKind.CSV,
        "source_label": "CSV client",
        "provider_id": unit_of_work.source_providers.provider.id,
        "purpose": "commercial_follow_up",
        "territory": "CA-QC",
        "obtained_at": NOW,
        "data_categories": ("business_identity", "email"),
        "idempotency_key": "same-key",
    }

    await use_case.execute(**common, external_reference="batch-1")
    with pytest.raises(IdempotencyKeyReused):
        await use_case.execute(**common, external_reference="batch-2")


@pytest.mark.asyncio
async def test_create_channel_generates_server_provenance_and_unknown_permission(
    context: TenantContext,
    unit_of_work: MemoryUnitOfWork,
) -> None:
    use_case = CreateContactChannelUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    channel = await use_case.execute(
        context=context,
        has_capability=True,
        channel_type=ContactChannelType.EMAIL,
        value=" Info@Exemple.ca ",
        prospect_id=unit_of_work.prospects.item.id,
        contact_id=None,
        source=ManualSourceCommand(purpose="commercial_follow_up", territory="CA-QC"),
    )

    permission = await unit_of_work.contact_permissions.get_by_channel(channel.id)
    assert channel.value_normalized == "info@exemple.ca"
    assert channel.provenance_id in unit_of_work.provenance.items
    assert permission is not None
    assert permission.status is ContactPermissionStatus.UNKNOWN
    assert len(unit_of_work.audit.events) == 2


@pytest.mark.asyncio
async def test_sales_can_restrict_but_cannot_allow(
    context: TenantContext,
    unit_of_work: MemoryUnitOfWork,
) -> None:
    channel = await CreateContactChannelUseCase(lambda _: unit_of_work, FixedClock()).execute(  # type: ignore[arg-type]
        context=context,
        has_capability=True,
        channel_type=ContactChannelType.EMAIL,
        value="qa@example.ca",
        prospect_id=unit_of_work.prospects.item.id,
        contact_id=None,
        source=ManualSourceCommand(purpose="commercial_follow_up", territory="CA-QC"),
    )
    permission = await unit_of_work.contact_permissions.get_by_channel(channel.id)
    assert permission is not None
    use_case = ChangeContactPermissionUseCase(lambda _: unit_of_work, FixedClock())  # type: ignore[arg-type]

    outcome = await use_case.execute(
        context=context,
        channel_id=channel.id,
        expected_version=permission.version,
        status=ContactPermissionStatus.DO_NOT_CONTACT,
        has_restrict_capability=True,
        has_allow_capability=False,
        reason="Demande explicite",
    )
    with pytest.raises(InsufficientCapability):
        await use_case.execute(
            context=context,
            channel_id=channel.id,
            expected_version=outcome.permission.version,
            status=ContactPermissionStatus.ALLOWED,
            has_restrict_capability=True,
            has_allow_capability=False,
            legal_basis_code="consent",
            provenance_id=uuid4(),
        )

    assert outcome.permission.status is ContactPermissionStatus.DO_NOT_CONTACT
    assert outcome.propagated_count == 1
