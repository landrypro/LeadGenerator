from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ...domain.audit import AuditAction
from ...domain.prospect import (
    AcquisitionStatus,
    ArchiveReasonCode,
    ImportDeclarationDraft,
    ImportDeclarationStatus,
    ImportDeclarationView,
    RetentionHoldDraft,
    RetentionHoldReasonCode,
    RetentionHoldReleaseReasonCode,
    RetentionHoldView,
    RetentionPolicyDraft,
    RetentionPolicyPatch,
    RetentionPolicyStatus,
    RetentionPolicyView,
    RetentionResourceType,
    RetentionReviewState,
    RetentionReviewView,
    import_declaration_reason_codes,
)
from ..audit_events import tenant_audit_event
from ..errors import (
    AcquisitionNotApproved,
    IdempotencyKeyReused,
    InsufficientCapability,
    ProspectComplianceResourceNotFound,
    ProspectResourceNotFound,
    ProspectVersionConflict,
    RetentionHoldAlreadyReleased,
)
from ..ports import Clock
from ..ports.prospect import ProspectUnitOfWorkFactory
from ..tenancy import TenantContext


@dataclass(frozen=True, slots=True)
class ArchivedProspectOutcome:
    prospect_id: UUID
    version: int
    contacts_archived: int
    channels_archived: int


@dataclass(frozen=True, slots=True)
class ArchivedContactOutcome:
    contact_id: UUID
    version: int
    channels_archived: int


@dataclass(frozen=True, slots=True)
class ArchivedChannelOutcome:
    channel_id: UUID
    version: int


class CreateRetentionPolicyUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        resource_type: RetentionResourceType,
        policy_code: str,
        label: str,
        review_after_days: int,
        archive_after_days: int | None,
        effective_from: datetime | None,
    ) -> RetentionPolicyView:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            policy = await unit_of_work.retention_policies.add(
                RetentionPolicyDraft(
                    organization_id=context.organization_id,
                    resource_type=resource_type,
                    policy_code=policy_code,
                    label=label,
                    review_after_days=review_after_days,
                    archive_after_days=archive_after_days,
                    effective_from=effective_from,
                    created_by=context.actor_id,
                ),
                now=now,
            )
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.RETENTION_POLICY_CREATED,
                    policy.id,
                    {"resource_type": policy.resource_type.value, "status": policy.status.value},
                )
            )
            await unit_of_work.commit()
            return policy


class UpdateRetentionPolicyUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        policy_id: UUID,
        patch: RetentionPolicyPatch,
    ) -> RetentionPolicyView:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            previous = await unit_of_work.retention_policies.get(policy_id)
            if previous is None:
                raise ProspectComplianceResourceNotFound
            updated = await unit_of_work.retention_policies.update(policy_id, patch, now=now)
            if updated is None:
                raise ProspectVersionConflict(previous.version)
            await unit_of_work.commit()
            return updated


class ActivateRetentionPolicyUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        policy_id: UUID,
        expected_version: int,
    ) -> RetentionPolicyView:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            previous = await unit_of_work.retention_policies.get(policy_id)
            if previous is None:
                raise ProspectComplianceResourceNotFound
            policy = await unit_of_work.retention_policies.activate(
                policy_id,
                expected_version=expected_version,
                now=now,
                approved_by=context.actor_id,
            )
            if policy is None:
                raise ProspectVersionConflict(previous.version)
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.RETENTION_POLICY_ACTIVATED,
                    policy.id,
                    {
                        "resource_type": policy.resource_type.value,
                        "previous_status": previous.status.value,
                        "new_status": policy.status.value,
                    },
                )
            )
            await unit_of_work.commit()
            return policy


class ListRetentionPoliciesUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        resource_type: RetentionResourceType | None,
        status: RetentionPolicyStatus | None,
        limit: int,
    ) -> tuple[RetentionPolicyView, ...]:
        _require_capability(has_capability)
        _validate_limit(limit)
        async with self._unit_of_work_factory(context) as unit_of_work:
            return await unit_of_work.retention_policies.list(resource_type=resource_type, status=status, limit=limit)


class GetRetentionPolicyUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        policy_id: UUID,
    ) -> RetentionPolicyView:
        _require_capability(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            policy = await unit_of_work.retention_policies.get(policy_id)
        if policy is None:
            raise ProspectComplianceResourceNotFound
        return policy


class ListRetentionReviewsUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        resource_type: RetentionResourceType | None,
        review_state: RetentionReviewState | None,
        due_before: datetime | None,
        limit: int,
    ) -> tuple[RetentionReviewView, ...]:
        _require_capability(has_capability)
        _validate_limit(limit)
        async with self._unit_of_work_factory(context) as unit_of_work:
            return await unit_of_work.retention_reviews.list(
                resource_type=resource_type,
                review_state=review_state,
                due_before=due_before,
                limit=limit,
            )


class PlaceRetentionHoldUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        resource_type: RetentionResourceType,
        resource_id: UUID,
        reason_code: RetentionHoldReasonCode,
        note: str | None,
        idempotency_key: str | None,
    ) -> RetentionHoldView:
        _require_capability(has_capability)
        fingerprint = _command_fingerprint(
            {
                "resource_type": resource_type.value,
                "resource_id": str(resource_id),
                "reason_code": reason_code.value,
                "note": note,
            }
        )
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            if idempotency_key:
                existing = await unit_of_work.retention_holds.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    if existing.command_fingerprint != fingerprint:
                        raise IdempotencyKeyReused
                    return existing
            hold = await unit_of_work.retention_holds.add(
                RetentionHoldDraft(
                    organization_id=context.organization_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    reason_code=reason_code,
                    note=note,
                    placed_by=context.actor_id,
                    idempotency_key=idempotency_key,
                    command_fingerprint=fingerprint,
                ),
                now=now,
            )
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.RETENTION_HOLD_PLACED,
                    hold.id,
                    {"resource_type": resource_type.value, "reason_code": reason_code.value},
                )
            )
            await unit_of_work.commit()
            return hold


class ReleaseRetentionHoldUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        hold_id: UUID,
        expected_version: int,
        release_reason_code: RetentionHoldReleaseReasonCode,
    ) -> RetentionHoldView:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            previous = await unit_of_work.retention_holds.get(hold_id)
            if previous is None:
                raise ProspectComplianceResourceNotFound
            if previous.released_at is not None:
                raise RetentionHoldAlreadyReleased
            hold = await unit_of_work.retention_holds.release(
                hold_id,
                expected_version=expected_version,
                release_reason_code=release_reason_code,
                released_by=context.actor_id,
                now=now,
            )
            if hold is None:
                raise ProspectVersionConflict(previous.version)
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.RETENTION_HOLD_RELEASED,
                    hold.id,
                    {"resource_type": hold.resource_type.value, "release_reason_code": release_reason_code.value},
                )
            )
            await unit_of_work.commit()
            return hold


class ListRetentionHoldsUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        resource_type: RetentionResourceType | None,
        resource_id: UUID | None,
        active_only: bool | None,
        limit: int,
    ) -> tuple[RetentionHoldView, ...]:
        _require_capability(has_capability)
        _validate_limit(limit)
        async with self._unit_of_work_factory(context) as unit_of_work:
            return await unit_of_work.retention_holds.list(
                resource_type=resource_type,
                resource_id=resource_id,
                active_only=active_only,
                limit=limit,
            )


class GetRetentionHoldUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        hold_id: UUID,
    ) -> RetentionHoldView:
        _require_capability(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            hold = await unit_of_work.retention_holds.get(hold_id)
        if hold is None:
            raise ProspectComplianceResourceNotFound
        return hold


class DeclareImportUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        acquisition_record_id: UUID,
        declaration_label: str,
        format_code: str,
        schema_code: str,
        declared_field_codes: tuple[str, ...],
        declared_data_categories: tuple[str, ...],
        estimated_row_count: int | None,
        declared_content_sha256: str | None,
        idempotency_key: str | None,
    ) -> ImportDeclarationView:
        _require_capability(has_capability)
        fingerprint = _command_fingerprint(
            {
                "acquisition_record_id": str(acquisition_record_id),
                "declaration_label": declaration_label,
                "format_code": format_code,
                "schema_code": schema_code,
                "declared_field_codes": sorted(declared_field_codes),
                "declared_data_categories": sorted(declared_data_categories),
                "estimated_row_count": estimated_row_count,
                "declared_content_sha256": declared_content_sha256,
            }
        )
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            if idempotency_key:
                existing = await unit_of_work.import_declarations.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    if existing.command_fingerprint != fingerprint:
                        raise IdempotencyKeyReused
                    return existing
            acquisition = await unit_of_work.acquisitions.get(acquisition_record_id)
            if acquisition is None or acquisition.status is not AcquisitionStatus.APPROVED:
                raise AcquisitionNotApproved
            reasons = import_declaration_reason_codes(
                acquisition,
                field_codes=declared_field_codes,
                data_categories=declared_data_categories,
            )
            status = ImportDeclarationStatus.QUARANTINED if reasons else ImportDeclarationStatus.DECLARED
            declaration = await unit_of_work.import_declarations.add(
                ImportDeclarationDraft(
                    organization_id=context.organization_id,
                    acquisition_record_id=acquisition_record_id,
                    declaration_label=declaration_label,
                    format_code=format_code,
                    schema_code=schema_code,
                    declared_field_codes=declared_field_codes,
                    declared_data_categories=declared_data_categories,
                    estimated_row_count=estimated_row_count,
                    declared_content_sha256=declared_content_sha256,
                    declared_by=context.actor_id,
                    idempotency_key=idempotency_key,
                    command_fingerprint=fingerprint,
                ),
                now=now,
                status=status.value,
                decision_reason_codes=tuple(reason.value for reason in reasons),
            )
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.IMPORT_DECLARATION_QUARANTINED
                    if status is ImportDeclarationStatus.QUARANTINED
                    else AuditAction.IMPORT_DECLARATION_DECLARED,
                    declaration.id,
                    _import_audit_metadata(status, tuple(reason.value for reason in reasons)),
                )
            )
            await unit_of_work.commit()
            return declaration


class ListImportDeclarationsUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self, *, context: TenantContext, has_capability: bool, limit: int
    ) -> tuple[ImportDeclarationView, ...]:
        _require_capability(has_capability)
        _validate_limit(limit)
        async with self._unit_of_work_factory(context) as unit_of_work:
            return await unit_of_work.import_declarations.list(limit=limit)


class GetImportDeclarationUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self, *, context: TenantContext, has_capability: bool, declaration_id: UUID
    ) -> ImportDeclarationView:
        _require_capability(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            declaration = await unit_of_work.import_declarations.get(declaration_id)
        if declaration is None:
            raise ProspectComplianceResourceNotFound
        return declaration


class CancelImportDeclarationUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self, *, context: TenantContext, has_capability: bool, declaration_id: UUID, expected_version: int
    ) -> ImportDeclarationView:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            previous = await unit_of_work.import_declarations.get(declaration_id)
            if previous is None:
                raise ProspectComplianceResourceNotFound
            declaration = await unit_of_work.import_declarations.cancel(
                declaration_id, expected_version=expected_version, now=now
            )
            if declaration is None:
                raise ProspectVersionConflict(previous.version)
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.IMPORT_DECLARATION_CANCELLED,
                    declaration.id,
                    {"status": declaration.status.value},
                )
            )
            await unit_of_work.commit()
            return declaration


class ArchiveImportDeclarationUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        declaration_id: UUID,
        expected_version: int,
        archive_reason_code: ArchiveReasonCode,
    ) -> ImportDeclarationView:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            previous = await unit_of_work.import_declarations.get(declaration_id)
            if previous is None:
                raise ProspectComplianceResourceNotFound
            declaration = await unit_of_work.import_declarations.archive(
                declaration_id,
                expected_version=expected_version,
                archive_reason_code=archive_reason_code.value,
                now=now,
            )
            if declaration is None:
                raise ProspectVersionConflict(previous.version)
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.IMPORT_DECLARATION_ARCHIVED,
                    declaration.id,
                    {"previous_status": previous.status.value, "archive_reason_code": archive_reason_code.value},
                )
            )
            await unit_of_work.commit()
            return declaration


class ArchiveProspectUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        prospect_id: UUID,
        expected_version: int,
        archive_reason_code: ArchiveReasonCode,
    ) -> ArchivedProspectOutcome:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            previous = await unit_of_work.prospects.get(prospect_id)
            if previous is None:
                raise ProspectResourceNotFound
            result = await unit_of_work.prospects.archive_with_cascade(
                prospect_id,
                expected_version=expected_version,
                now=now,
                reason_code=archive_reason_code.value,
            )
            if result is None:
                raise ProspectVersionConflict(previous.version)
            prospect, contacts_archived, channels_archived = result
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.PROSPECT_ARCHIVED,
                    prospect.id,
                    {
                        "previous_version": previous.version,
                        "archive_reason_code": archive_reason_code.value,
                        "contacts_archived": contacts_archived,
                        "channels_archived": channels_archived,
                    },
                )
            )
            await unit_of_work.commit()
            return ArchivedProspectOutcome(prospect.id, prospect.version, contacts_archived, channels_archived)


class ArchiveContactUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        contact_id: UUID,
        expected_version: int,
        archive_reason_code: ArchiveReasonCode,
    ) -> ArchivedContactOutcome:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            previous = await unit_of_work.contacts.get(contact_id)
            if previous is None:
                raise ProspectComplianceResourceNotFound
            result = await unit_of_work.contacts.archive(
                contact_id,
                expected_version=expected_version,
                now=now,
                reason_code=archive_reason_code.value,
            )
            if result is None:
                raise ProspectVersionConflict(previous.version)
            contact, channels_archived = result
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.CONTACT_ARCHIVED,
                    contact.id,
                    {
                        "previous_version": previous.version,
                        "archive_reason_code": archive_reason_code.value,
                        "channels_archived": channels_archived,
                    },
                )
            )
            await unit_of_work.commit()
            return ArchivedContactOutcome(contact.id, contact.version, channels_archived)


class ArchiveContactChannelUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        channel_id: UUID,
        expected_version: int,
        archive_reason_code: ArchiveReasonCode,
    ) -> ArchivedChannelOutcome:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            previous = await unit_of_work.contact_channels.get(channel_id)
            if previous is None:
                raise ProspectComplianceResourceNotFound
            channel = await unit_of_work.contact_channels.archive(
                channel_id,
                expected_version=expected_version,
                now=now,
                reason_code=archive_reason_code.value,
            )
            if channel is None:
                raise ProspectVersionConflict(previous.version)
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.CONTACT_CHANNEL_ARCHIVED,
                    channel.id,
                    {"previous_version": previous.version, "archive_reason_code": archive_reason_code.value},
                )
            )
            await unit_of_work.commit()
            return ArchivedChannelOutcome(channel.id, channel.version)


def _require_capability(has_capability: bool) -> None:
    if not has_capability:
        raise InsufficientCapability


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= 100:
        raise ValueError("limit doit etre compris entre 1 et 100.")


def _command_fingerprint(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _import_audit_metadata(status: ImportDeclarationStatus, reason_codes: tuple[str, ...]) -> dict[str, object]:
    if status is ImportDeclarationStatus.QUARANTINED:
        return {"status": status.value, "decision_reason_codes": reason_codes}
    return {"status": status.value}
