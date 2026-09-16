from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ...domain.audit import AuditAction
from ...domain.prospect import (
    LEGAL_BASIS_CODES,
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
    ProvenanceDraft,
    ProvenanceSourceKind,
    ProvenanceView,
    SourceProviderDraft,
    SourceProviderPatch,
    SourceProviderStatus,
    SourceProviderView,
    provider_quarantine_reason,
)
from ..audit_events import tenant_audit_event
from ..errors import (
    AcquisitionNotApproved,
    ChannelDuplicate,
    IdempotencyKeyReused,
    InsufficientCapability,
    InvalidPermissionTransition,
    ProspectComplianceResourceNotFound,
    ProspectResourceNotFound,
    ProspectVersionConflict,
)
from ..ports import Clock
from ..ports.prospect import ProspectUnitOfWork, ProspectUnitOfWorkFactory
from ..tenancy import TenantContext

MANUAL_SOURCE_LABEL = "manual:user_entry"
RESTRICTIVE_STATUSES = {ContactPermissionStatus.DO_NOT_CONTACT, ContactPermissionStatus.OPTED_OUT}
_EMAIL_PATTERN = re.compile(r"^[^@\s\x00-\x1f\x7f]{1,64}@[^@\s\x00-\x1f\x7f]{1,253}$", re.ASCII)
_PHONE_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$", re.ASCII)
_LINKEDIN_PATTERN = re.compile(r"^https://([a-z0-9-]+\.)?linkedin\.com/.+", re.IGNORECASE)
_FACEBOOK_PATTERN = re.compile(r"^https://([a-z0-9-]+\.)?facebook\.com/.+", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ManualSourceCommand:
    purpose: str
    territory: str


@dataclass(frozen=True, slots=True)
class AcquisitionSourceCommand:
    acquisition_id: UUID


type SourceCommand = ManualSourceCommand | AcquisitionSourceCommand


@dataclass(frozen=True, slots=True)
class PermissionChangeOutcome:
    permission: ContactPermissionView
    propagated_count: int


class CreateSourceProviderUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        source_kind: ProvenanceSourceKind,
        label: str,
    ) -> SourceProviderView:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            provider = await unit_of_work.source_providers.add(
                SourceProviderDraft(
                    organization_id=context.organization_id,
                    source_kind=source_kind,
                    label=label,
                    status=SourceProviderStatus.DRAFT,
                ),
                now=now,
            )
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.SOURCE_PROVIDER_CREATED,
                    provider.id,
                    {"source_kind": provider.source_kind.value, "status": provider.status.value},
                )
            )
            await unit_of_work.commit()
            return provider


class UpdateSourceProviderUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        provider_id: UUID,
        patch: SourceProviderPatch,
        has_capability: bool,
    ) -> SourceProviderView:
        _require_capability(has_capability)
        changed_fields = _provider_changed_fields(patch)
        if not changed_fields and patch.status is None and patch.rights_attested is None:
            raise ValueError("La modification fournisseur est vide.")
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            previous = await unit_of_work.source_providers.get(provider_id)
            if previous is None:
                raise ProspectComplianceResourceNotFound
            updated = await unit_of_work.source_providers.update(provider_id, patch, now=now)
            if updated is None:
                raise ProspectVersionConflict(previous.version)
            if previous.status is not updated.status:
                await unit_of_work.audit.record(
                    tenant_audit_event(
                        context,
                        AuditAction.SOURCE_PROVIDER_STATUS_CHANGED,
                        provider_id,
                        {"previous_status": previous.status.value, "new_status": updated.status.value},
                    )
                )
            if changed_fields:
                await unit_of_work.audit.record(
                    tenant_audit_event(
                        context,
                        AuditAction.SOURCE_PROVIDER_UPDATED,
                        provider_id,
                        {"changed_fields": tuple(changed_fields)},
                    )
                )
            await unit_of_work.commit()
            return updated


class ListSourceProvidersUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        limit: int,
    ) -> tuple[SourceProviderView, ...]:
        _require_capability(has_capability)
        _validate_limit(limit)
        async with self._unit_of_work_factory(context) as unit_of_work:
            return await unit_of_work.source_providers.list_active(limit=limit)


class GetSourceProviderUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        provider_id: UUID,
        has_capability: bool,
    ) -> SourceProviderView:
        _require_capability(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            provider = await unit_of_work.source_providers.get(provider_id)
        if provider is None:
            raise ProspectComplianceResourceNotFound
        return provider


class DeclareAcquisitionUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        source_kind: ProvenanceSourceKind,
        source_label: str,
        provider_id: UUID,
        purpose: str,
        territory: str,
        obtained_at: datetime,
        data_categories: tuple[str, ...],
        external_reference: str | None,
        idempotency_key: str | None,
    ) -> AcquisitionRecordView:
        _require_capability(has_capability)
        now = self._clock.now()
        fingerprint = _command_fingerprint(
            {
                "source_kind": source_kind.value,
                "source_label": source_label,
                "provider_id": str(provider_id),
                "purpose": purpose,
                "territory": territory,
                "obtained_at": obtained_at.isoformat(),
                "data_categories": sorted(data_categories),
                "external_reference": external_reference,
            }
        )
        async with self._unit_of_work_factory(context) as unit_of_work:
            if idempotency_key:
                existing = await unit_of_work.acquisitions.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    if existing.command_fingerprint != fingerprint:
                        raise IdempotencyKeyReused
                    return existing
            provider = await unit_of_work.source_providers.get(provider_id)
            if provider is None:
                raise ProspectComplianceResourceNotFound
            draft = AcquisitionDraft(
                organization_id=context.organization_id,
                source_kind=source_kind,
                source_label=source_label,
                provider_id=provider_id,
                purpose=purpose,
                territory=territory,
                obtained_at=obtained_at,
                declared_by=context.actor_id,
                data_categories=data_categories,
                external_reference=external_reference,
                idempotency_key=idempotency_key,
                command_fingerprint=fingerprint,
            )
            reason = provider_quarantine_reason(
                provider,
                source_kind=source_kind,
                purpose=purpose,
                territory=territory,
                data_categories=data_categories,
                at=now,
            )
            status = AcquisitionStatus.QUARANTINED if reason else AcquisitionStatus.APPROVED
            acquisition = await unit_of_work.acquisitions.add(
                draft,
                now=now,
                status=status.value,
                decision_reason_code=reason.value if reason else None,
                decided_by=context.actor_id,
            )
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.ACQUISITION_DECLARED,
                    acquisition.id,
                    {"source_kind": source_kind.value, "status": status.value},
                )
            )
            if reason is not None:
                await unit_of_work.audit.record(
                    tenant_audit_event(
                        context,
                        AuditAction.ACQUISITION_QUARANTINED,
                        acquisition.id,
                        {"source_kind": source_kind.value, "reason_code": reason.value},
                    )
                )
            await unit_of_work.commit()
            return acquisition


class ListAcquisitionsUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        has_capability: bool,
        limit: int,
    ) -> tuple[AcquisitionRecordView, ...]:
        _require_capability(has_capability)
        _validate_limit(limit)
        async with self._unit_of_work_factory(context) as unit_of_work:
            return await unit_of_work.acquisitions.list_recent(limit=limit)


class GetAcquisitionUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        acquisition_id: UUID,
        has_capability: bool,
    ) -> AcquisitionRecordView:
        _require_capability(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            acquisition = await unit_of_work.acquisitions.get(acquisition_id)
        if acquisition is None:
            raise ProspectComplianceResourceNotFound
        return acquisition


class DecideAcquisitionUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        acquisition_id: UUID,
        expected_version: int,
        approve: bool,
        has_capability: bool,
        reason_code: str | None = None,
    ) -> AcquisitionRecordView:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            previous = await unit_of_work.acquisitions.get(acquisition_id)
            if previous is None:
                raise ProspectComplianceResourceNotFound
            status = AcquisitionStatus.APPROVED if approve else AcquisitionStatus.REJECTED
            updated = await unit_of_work.acquisitions.decide(
                acquisition_id,
                expected_version=expected_version,
                status=status.value,
                now=now,
                decided_by=context.actor_id,
                decision_reason_code=None if approve else reason_code,
            )
            if updated is None:
                raise ProspectVersionConflict(previous.version)
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.ACQUISITION_APPROVED if approve else AuditAction.ACQUISITION_REJECTED,
                    acquisition_id,
                    {"previous_status": previous.status.value, "new_status": updated.status.value},
                )
            )
            await unit_of_work.commit()
            return updated


class CreateContactUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        prospect_id: UUID,
        display_name: str,
        role_label: str | None,
        source: SourceCommand,
        has_capability: bool,
    ) -> ContactView:
        _require_capability(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            prospect = await unit_of_work.prospects.get(prospect_id)
            if prospect is None:
                raise ProspectResourceNotFound
            provenance = await _create_provenance(unit_of_work, context, source, now=now)
            contact = await unit_of_work.contacts.add(
                ContactDraft(
                    organization_id=context.organization_id,
                    prospect_id=prospect_id,
                    display_name=display_name,
                    role_label=role_label,
                    provenance_id=provenance.id,
                ),
                now=now,
            )
            await unit_of_work.audit.record(
                tenant_audit_event(context, AuditAction.CONTACT_CREATED, contact.id, {"prospect_id": prospect_id})
            )
            await unit_of_work.commit()
            return contact


class ListContactsUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        prospect_id: UUID,
        has_capability: bool,
    ) -> tuple[ContactView, ...]:
        _require_capability(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            prospect = await unit_of_work.prospects.get(prospect_id)
            if prospect is None:
                raise ProspectResourceNotFound
            return await unit_of_work.contacts.list_for_prospect(prospect_id)


class ListProspectChannelsUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        prospect_id: UUID,
        has_capability: bool,
    ) -> tuple[ContactChannelView, ...]:
        _require_capability(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            prospect = await unit_of_work.prospects.get(prospect_id)
            if prospect is None:
                raise ProspectResourceNotFound
            return await unit_of_work.contact_channels.list_for_prospect(prospect_id)


class ListContactChannelsUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        contact_id: UUID,
        has_capability: bool,
    ) -> tuple[ContactChannelView, ...]:
        _require_capability(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            contact = await unit_of_work.contacts.get(contact_id)
            if contact is None:
                raise ProspectComplianceResourceNotFound
            return await unit_of_work.contact_channels.list_for_contact(contact_id)


class CreateContactChannelUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        channel_type: ContactChannelType,
        value: str,
        source: SourceCommand,
        has_capability: bool,
        prospect_id: UUID | None = None,
        contact_id: UUID | None = None,
    ) -> ContactChannelView:
        _require_capability(has_capability)
        now = self._clock.now()
        value_normalized = _normalize_channel_value(channel_type, value)
        async with self._unit_of_work_factory(context) as unit_of_work:
            if contact_id is not None:
                contact = await unit_of_work.contacts.get(contact_id)
                if contact is None:
                    raise ProspectComplianceResourceNotFound
            if prospect_id is not None:
                prospect = await unit_of_work.prospects.get(prospect_id)
                if prospect is None:
                    raise ProspectResourceNotFound
            duplicate = await unit_of_work.contact_channels.find_duplicate(
                channel_type=channel_type.value,
                value_normalized=value_normalized,
                prospect_id=prospect_id,
                contact_id=contact_id,
            )
            if duplicate is not None:
                raise ChannelDuplicate
            provenance = await _create_provenance(unit_of_work, context, source, now=now)
            channel = await unit_of_work.contact_channels.add(
                ContactChannelDraft(
                    organization_id=context.organization_id,
                    prospect_id=prospect_id,
                    contact_id=contact_id,
                    channel_type=channel_type,
                    value=value,
                    value_normalized=value_normalized,
                    provenance_id=provenance.id,
                    created_by=context.actor_id,
                ),
                now=now,
            )
            await unit_of_work.contact_permissions.add_unknown(
                channel.id, organization_id=context.organization_id, now=now
            )
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.CHANNEL_CREATED,
                    channel.id,
                    {"channel_type": channel_type.value, "target_type": "contact" if contact_id else "prospect"},
                )
            )
            await unit_of_work.commit()
            return channel


class GetContactPermissionUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        *,
        context: TenantContext,
        channel_id: UUID,
        has_capability: bool,
    ) -> ContactPermissionView:
        _require_capability(has_capability)
        async with self._unit_of_work_factory(context) as unit_of_work:
            permission = await unit_of_work.contact_permissions.get_by_channel(channel_id)
        if permission is None:
            raise ProspectComplianceResourceNotFound
        return permission


class ChangeContactPermissionUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        channel_id: UUID,
        expected_version: int,
        status: ContactPermissionStatus,
        has_restrict_capability: bool,
        has_allow_capability: bool,
        legal_basis_code: str | None = None,
        provenance_id: UUID | None = None,
        reason: str | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> PermissionChangeOutcome:
        _validate_permission_command(
            status,
            has_restrict_capability=has_restrict_capability,
            has_allow_capability=has_allow_capability,
            legal_basis_code=legal_basis_code,
            provenance_id=provenance_id,
        )
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as unit_of_work:
            channel = await unit_of_work.contact_channels.get(channel_id)
            previous = await unit_of_work.contact_permissions.get_by_channel(channel_id)
            if channel is None or previous is None:
                raise ProspectComplianceResourceNotFound
            permission = await unit_of_work.contact_permissions.update(
                previous.id,
                expected_version=expected_version,
                status=status,
                now=now,
                decided_by=context.actor_id,
                legal_basis_code=legal_basis_code,
                provenance_id=provenance_id,
                reason=reason,
                valid_from=valid_from,
                valid_until=valid_until,
            )
            if permission is None:
                raise ProspectVersionConflict(previous.version)
            propagated_count = 0
            if status in RESTRICTIVE_STATUSES:
                propagated_count = await unit_of_work.contact_permissions.apply_restriction_to_value(
                    channel_type=channel.channel_type.value,
                    value_normalized=channel.value_normalized,
                    status=status,
                    now=now,
                    decided_by=context.actor_id,
                    reason=reason,
                )
            await unit_of_work.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.CONTACT_PERMISSION_CHANGED,
                    permission.id,
                    {
                        "previous_status": previous.status.value,
                        "new_status": permission.status.value,
                        "propagated_count": propagated_count,
                    },
                )
            )
            await unit_of_work.commit()
            return PermissionChangeOutcome(permission=permission, propagated_count=propagated_count)


async def _create_provenance(
    unit_of_work: ProspectUnitOfWork,
    context: TenantContext,
    source: SourceCommand,
    *,
    now: datetime,
) -> ProvenanceView:
    provenance_repository = unit_of_work.provenance
    audit = unit_of_work.audit
    if isinstance(source, ManualSourceCommand):
        provenance = await provenance_repository.add(
            ProvenanceDraft(
                organization_id=context.organization_id,
                source_kind=ProvenanceSourceKind.MANUAL,
                source_label=MANUAL_SOURCE_LABEL,
                purpose=source.purpose,
                territory=source.territory,
                obtained_at=now,
                attested_by=context.actor_id,
            ),
            now=now,
        )
    else:
        acquisition = await unit_of_work.acquisitions.get(source.acquisition_id)
        if acquisition is None:
            raise ProspectComplianceResourceNotFound
        if acquisition.status is AcquisitionStatus.QUARANTINED:
            raise AcquisitionNotApproved
        if acquisition.status is not AcquisitionStatus.APPROVED:
            raise AcquisitionNotApproved
        provenance = await provenance_repository.add(
            ProvenanceDraft(
                organization_id=context.organization_id,
                source_kind=acquisition.source_kind,
                source_label=acquisition.source_label,
                provider_id=acquisition.provider_id,
                purpose=acquisition.purpose,
                territory=acquisition.territory,
                obtained_at=acquisition.obtained_at,
                attested_by=context.actor_id,
                acquisition_record_id=acquisition.id,
            ),
            now=now,
        )
    await audit.record(
        tenant_audit_event(
            context,
            AuditAction.PROVENANCE_RECORDED,
            provenance.id,
            {"source_kind": provenance.source_kind.value},
        )
    )
    return provenance


def _require_capability(has_capability: bool) -> None:
    if not has_capability:
        raise InsufficientCapability


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= 100:
        raise ValueError("limit doit etre compris entre 1 et 100.")


def _provider_changed_fields(patch: SourceProviderPatch) -> tuple[str, ...]:
    names = (
        "allowed_data_categories",
        "allowed_purposes",
        "allowed_territories",
        "label",
        "terms_reference",
        "terms_url",
        "valid_from",
        "valid_until",
    )
    return tuple(name for name in names if getattr(patch, name) is not None)


def _command_fingerprint(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_channel_value(channel_type: ContactChannelType, value: str) -> str:
    value = " ".join(value.split())
    if channel_type is ContactChannelType.EMAIL:
        local, separator, domain = value.rpartition("@")
        if not separator:
            raise ValueError("Courriel invalide.")
        try:
            normalized = f"{local.casefold()}@{domain.encode('idna').decode('ascii').casefold()}"
        except UnicodeError as error:
            raise ValueError("Courriel invalide.") from error
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Courriel invalide.")
        return normalized
    if channel_type is ContactChannelType.PHONE:
        normalized = re.sub(r"[\s().-]", "", value)
        if not _PHONE_PATTERN.fullmatch(normalized):
            raise ValueError("Telephone invalide.")
        return normalized
    if channel_type is ContactChannelType.LINKEDIN:
        if not _LINKEDIN_PATTERN.fullmatch(value):
            raise ValueError("Profil LinkedIn invalide.")
        return value.casefold()
    if channel_type is ContactChannelType.FACEBOOK:
        if not _FACEBOOK_PATTERN.fullmatch(value):
            raise ValueError("Profil Facebook invalide.")
        return value.casefold()
    if not value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("Valeur de canal invalide.")
    return value.casefold()


def _validate_permission_command(
    status: ContactPermissionStatus,
    *,
    has_restrict_capability: bool,
    has_allow_capability: bool,
    legal_basis_code: str | None,
    provenance_id: UUID | None,
) -> None:
    if status is ContactPermissionStatus.ALLOWED:
        if not has_allow_capability:
            raise InsufficientCapability
        if legal_basis_code not in LEGAL_BASIS_CODES or provenance_id is None:
            raise InvalidPermissionTransition
        return
    if status in RESTRICTIVE_STATUSES:
        if not has_restrict_capability:
            raise InsufficientCapability
        return
    raise InvalidPermissionTransition
