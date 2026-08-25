from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from ...domain.prospect import (
    AcquisitionDraft,
    AcquisitionRecordView,
    ContactChannelDraft,
    ContactChannelView,
    ContactDraft,
    ContactPermissionStatus,
    ContactPermissionView,
    ContactView,
    ImportDeclarationDraft,
    ImportDeclarationView,
    ProspectDraft,
    ProspectProfilePatch,
    ProspectView,
    ProvenanceDraft,
    ProvenanceView,
    RetentionHoldDraft,
    RetentionHoldReleaseReasonCode,
    RetentionHoldView,
    RetentionPolicyDraft,
    RetentionPolicyPatch,
    RetentionPolicyStatus,
    RetentionPolicyView,
    RetentionResourceType,
    RetentionReviewState,
    RetentionReviewView,
    SourceProviderDraft,
    SourceProviderPatch,
    SourceProviderView,
)
from ..models import GoogleAccessOwner
from ..tenancy import TenantContext
from .audit import AuditRecorder


class ProspectRepository(Protocol):
    async def add(self, draft: ProspectDraft, *, now: datetime) -> ProspectView: ...

    async def get(self, prospect_id: UUID) -> ProspectView | None: ...

    async def get_by_google_place_id(self, google_place_id: str) -> ProspectView | None: ...

    async def list_active(
        self,
        *,
        limit: int,
        after_created_at: datetime | None = None,
        after_id: UUID | None = None,
        offset: int = 0,
        include_archived: bool = False,
        search_text: str | None = None,
        origin: str | None = None,
        owner_id: UUID | None = None,
        priority: int | None = None,
    ) -> tuple[ProspectView, ...]: ...

    async def update(
        self,
        prospect_id: UUID,
        *,
        expected_version: int,
        patch: ProspectProfilePatch,
        profile_provenance_id: UUID,
        now: datetime,
    ) -> ProspectView | None: ...

    async def archive(self, prospect_id: UUID, *, expected_version: int, now: datetime) -> ProspectView | None: ...

    async def archive_with_cascade(
        self, prospect_id: UUID, *, expected_version: int, now: datetime, reason_code: str = "other"
    ) -> tuple[ProspectView, int, int] | None: ...


class ContactRepository(Protocol):
    async def add(self, draft: ContactDraft, *, now: datetime) -> ContactView: ...

    async def get(self, contact_id: UUID) -> ContactView | None: ...

    async def list_for_prospect(self, prospect_id: UUID) -> tuple[ContactView, ...]: ...

    async def archive(
        self, contact_id: UUID, *, expected_version: int, now: datetime, reason_code: str = "other"
    ) -> tuple[ContactView, int] | None: ...


class ContactChannelRepository(Protocol):
    async def add(self, draft: ContactChannelDraft, *, now: datetime) -> ContactChannelView: ...

    async def get(self, channel_id: UUID) -> ContactChannelView | None: ...

    async def list_for_prospect(self, prospect_id: UUID) -> tuple[ContactChannelView, ...]: ...

    async def list_for_contact(self, contact_id: UUID) -> tuple[ContactChannelView, ...]: ...

    async def find_by_normalized_value(
        self,
        *,
        channel_type: str,
        value_normalized: str,
    ) -> tuple[ContactChannelView, ...]: ...

    async def find_duplicate(
        self,
        *,
        channel_type: str,
        value_normalized: str,
        prospect_id: UUID | None,
        contact_id: UUID | None,
    ) -> ContactChannelView | None: ...

    async def archive(
        self, channel_id: UUID, *, expected_version: int, now: datetime, reason_code: str = "other"
    ) -> ContactChannelView | None: ...


class ContactPermissionRepository(Protocol):
    async def add_unknown(self, channel_id: UUID, *, organization_id: UUID, now: datetime) -> ContactPermissionView: ...

    async def get_by_channel(self, channel_id: UUID) -> ContactPermissionView | None: ...

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
    ) -> ContactPermissionView | None: ...

    async def apply_restriction_to_value(
        self,
        *,
        channel_type: str,
        value_normalized: str,
        status: ContactPermissionStatus,
        now: datetime,
        decided_by: UUID,
        reason: str | None,
    ) -> int: ...


class ProvenanceRepository(Protocol):
    async def add(self, draft: ProvenanceDraft, *, now: datetime) -> ProvenanceView: ...

    async def get(self, provenance_id: UUID) -> ProvenanceView | None: ...


class SourceProviderRepository(Protocol):
    async def add(self, draft: SourceProviderDraft, *, now: datetime) -> SourceProviderView: ...

    async def get(self, provider_id: UUID) -> SourceProviderView | None: ...

    async def list_active(self, *, limit: int, offset: int = 0) -> tuple[SourceProviderView, ...]: ...

    async def update(
        self, provider_id: UUID, patch: SourceProviderPatch, *, now: datetime
    ) -> SourceProviderView | None: ...


class AcquisitionRepository(Protocol):
    async def add(
        self,
        draft: AcquisitionDraft,
        *,
        now: datetime,
        status: str,
        decision_reason_code: str | None = None,
        decided_by: UUID | None = None,
    ) -> AcquisitionRecordView: ...

    async def get(self, acquisition_id: UUID) -> AcquisitionRecordView | None: ...

    async def get_by_idempotency_key(self, idempotency_key: str) -> AcquisitionRecordView | None: ...

    async def list_recent(self, *, limit: int, offset: int = 0) -> tuple[AcquisitionRecordView, ...]: ...

    async def decide(
        self,
        acquisition_id: UUID,
        *,
        expected_version: int,
        status: str,
        now: datetime,
        decided_by: UUID,
        decision_reason_code: str | None = None,
    ) -> AcquisitionRecordView | None: ...


class RetentionPolicyRepository(Protocol):
    async def add(self, draft: RetentionPolicyDraft, *, now: datetime) -> RetentionPolicyView: ...

    async def get(self, policy_id: UUID) -> RetentionPolicyView | None: ...

    async def list(
        self,
        *,
        resource_type: RetentionResourceType | None = None,
        status: RetentionPolicyStatus | None = None,
        limit: int,
        offset: int = 0,
    ) -> tuple[RetentionPolicyView, ...]: ...

    async def update(
        self, policy_id: UUID, patch: RetentionPolicyPatch, *, now: datetime
    ) -> RetentionPolicyView | None: ...

    async def activate(
        self, policy_id: UUID, *, expected_version: int, now: datetime, approved_by: UUID
    ) -> RetentionPolicyView | None: ...


class RetentionReviewRepository(Protocol):
    async def list(
        self,
        *,
        resource_type: RetentionResourceType | None,
        review_state: RetentionReviewState | None,
        due_before: datetime | None,
        limit: int,
        offset: int = 0,
    ) -> tuple[RetentionReviewView, ...]: ...


class RetentionHoldRepository(Protocol):
    async def add(self, draft: RetentionHoldDraft, *, now: datetime) -> RetentionHoldView: ...

    async def get(self, hold_id: UUID) -> RetentionHoldView | None: ...

    async def get_by_idempotency_key(self, idempotency_key: str) -> RetentionHoldView | None: ...

    async def has_active_hold(self, resource_type: RetentionResourceType, resource_id: UUID) -> bool: ...

    async def list(
        self,
        *,
        resource_type: RetentionResourceType | None = None,
        resource_id: UUID | None = None,
        active_only: bool | None = None,
        limit: int,
        offset: int = 0,
    ) -> tuple[RetentionHoldView, ...]: ...

    async def release(
        self,
        hold_id: UUID,
        *,
        expected_version: int,
        release_reason_code: RetentionHoldReleaseReasonCode,
        released_by: UUID,
        now: datetime,
    ) -> RetentionHoldView | None: ...


class ImportDeclarationRepository(Protocol):
    async def add(
        self,
        draft: ImportDeclarationDraft,
        *,
        now: datetime,
        status: str,
        decision_reason_codes: tuple[str, ...],
    ) -> ImportDeclarationView: ...

    async def get(self, declaration_id: UUID) -> ImportDeclarationView | None: ...

    async def get_by_idempotency_key(self, idempotency_key: str) -> ImportDeclarationView | None: ...

    async def list(self, *, limit: int, offset: int = 0) -> tuple[ImportDeclarationView, ...]: ...

    async def cancel(
        self, declaration_id: UUID, *, expected_version: int, now: datetime
    ) -> ImportDeclarationView | None: ...

    async def archive(
        self, declaration_id: UUID, *, expected_version: int, archive_reason_code: str, now: datetime
    ) -> ImportDeclarationView | None: ...


class ProspectUnitOfWork(Protocol):
    @property
    def prospects(self) -> ProspectRepository: ...

    @property
    def contacts(self) -> ContactRepository: ...

    @property
    def contact_channels(self) -> ContactChannelRepository: ...

    @property
    def contact_permissions(self) -> ContactPermissionRepository: ...

    @property
    def provenance(self) -> ProvenanceRepository: ...

    @property
    def source_providers(self) -> SourceProviderRepository: ...

    @property
    def acquisitions(self) -> AcquisitionRepository: ...

    @property
    def retention_policies(self) -> RetentionPolicyRepository: ...

    @property
    def retention_reviews(self) -> RetentionReviewRepository: ...

    @property
    def retention_holds(self) -> RetentionHoldRepository: ...

    @property
    def import_declarations(self) -> ImportDeclarationRepository: ...

    @property
    def audit(self) -> AuditRecorder: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


type ProspectUnitOfWorkFactory = Callable[[TenantContext], ProspectUnitOfWork]


class GoogleSelectionGrantStore(Protocol):
    async def issue(self, place_ids: tuple[str, ...], owner: GoogleAccessOwner, *, now: datetime) -> str: ...

    async def resolve(self, token: str, owner: GoogleAccessOwner, *, now: datetime) -> tuple[str, ...]: ...
