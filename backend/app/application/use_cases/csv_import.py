from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from ...domain.audit import AuditAction
from ...domain.csv_import import (
    CSV_IMPORT_MAPPING_FIELDS,
    CsvImportQuarantineView,
    CsvImportRowState,
    CsvImportRunView,
    CsvImportSessionView,
    CsvImportStatus,
)
from ...domain.prospect import (
    AcquisitionRecordView,
    AcquisitionStatus,
    ContactChannelDraft,
    ContactChannelType,
    ContactDraft,
    ProspectDraft,
    ProspectOrigin,
    ProspectProfilePatch,
    ProspectView,
    ProvenanceDraft,
    ProvenanceSourceKind,
)
from ..audit_events import tenant_audit_event
from ..errors import (
    AcquisitionNotApproved,
    IdempotencyKeyReused,
    InsufficientCapability,
    ProspectComplianceResourceNotFound,
    ProspectVersionConflict,
)
from ..ports import Clock
from ..ports.csv_import import TemporaryCsvFileStore
from ..ports.prospect import ProspectUnitOfWork, ProspectUnitOfWorkFactory
from ..tenancy import TenantContext

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 5_000
MAX_COLUMNS = 50
MAX_CELL_LENGTH = 4_096
PREVIEW_ROWS = 100
FILE_TTL = timedelta(hours=24)
_CHANNEL_FIELDS = {
    "email": ContactChannelType.EMAIL,
    "phone": ContactChannelType.PHONE,
    "linkedin_profile": ContactChannelType.LINKEDIN,
    "facebook_profile": ContactChannelType.FACEBOOK,
}


@dataclass(frozen=True, slots=True)
class CsvImportPreview:
    session: CsvImportSessionView
    rows: tuple[dict[str, str], ...]


@dataclass(frozen=True, slots=True)
class CsvImportValidation:
    session: CsvImportSessionView
    row_count: int
    ready_count: int
    duplicate_count: int
    review_count: int
    quarantined_count: int


class UploadCsvImportUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, file_store: TemporaryCsvFileStore, clock: Clock
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._file_store = file_store
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        declaration_id: UUID,
        chunks: AsyncIterator[bytes],
        has_capability: bool,
    ) -> CsvImportPreview:
        _require(has_capability)
        await self._file_store.cleanup_expired(max_age_seconds=int(FILE_TTL.total_seconds()))
        file_ref, digest, byte_size = await self._file_store.save(chunks)
        try:
            content = await self._require_content(file_ref)
            headers, rows = _parse_csv(content)
            now = self._clock.now()
            async with self._unit_of_work_factory(context) as uow:
                declaration = await uow.import_declarations.get(declaration_id)
                if declaration is None:
                    raise ProspectComplianceResourceNotFound
                acquisition = await uow.acquisitions.get(declaration.acquisition_record_id)
                if (
                    acquisition is None
                    or acquisition.status is not AcquisitionStatus.APPROVED
                    or acquisition.source_kind is not ProvenanceSourceKind.CSV
                ):
                    raise AcquisitionNotApproved
                if declaration.status.value != "declared":
                    raise ValueError("La déclaration d’import ne permet plus de téléversement.")
                session = await uow.csv_imports.add_session(
                    declaration_id=declaration_id,
                    file_ref=file_ref,
                    content_sha256=digest,
                    byte_size=byte_size,
                    headers=headers,
                    now=now,
                    expires_at=now + FILE_TTL,
                )
                await uow.audit.record(
                    tenant_audit_event(
                        context,
                        AuditAction.IMPORT_FILE_UPLOADED,
                        session.id,
                        {"byte_size": byte_size, "header_count": len(headers)},
                    )
                )
                await uow.commit()
            return CsvImportPreview(session=session, rows=tuple(rows[:PREVIEW_ROWS]))
        except BaseException:
            await self._file_store.delete(file_ref)
            raise

    async def _require_content(self, file_ref: str) -> bytes:
        content = await self._file_store.read(file_ref)
        if content is None:
            raise ValueError("Le fichier temporaire est introuvable.")
        return content


class GetCsvImportPreviewUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, file_store: TemporaryCsvFileStore, clock: Clock
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._file_store = file_store
        self._clock = clock

    async def execute(self, *, context: TenantContext, session_id: UUID, has_capability: bool) -> CsvImportPreview:
        _require(has_capability)
        async with self._unit_of_work_factory(context) as uow:
            session = await uow.csv_imports.get_session(session_id)
        session = _ensure_available(session, self._clock.now())
        content = await self._file_store.read(session.file_ref)
        if content is None:
            raise ValueError("Le fichier temporaire a expiré.")
        headers, rows = _parse_csv(content)
        if headers != session.headers:
            raise ValueError("Le fichier temporaire ne correspond plus à sa session.")
        return CsvImportPreview(session=session, rows=tuple(rows[:PREVIEW_ROWS]))


class MapCsvImportUseCase:
    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        session_id: UUID,
        expected_version: int,
        mapping: dict[str, str],
        has_capability: bool,
    ) -> CsvImportSessionView:
        _require(has_capability)
        normalized = _validate_mapping(mapping)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as uow:
            session = await uow.csv_imports.get_session(session_id)
            session = _ensure_available(session, now)
            if any(column not in session.headers for column in normalized):
                raise ValueError("Le mapping contient une colonne absente du fichier.")
            declaration = await uow.import_declarations.get(session.declaration_id)
            if declaration is None:
                raise ProspectComplianceResourceNotFound
            if not set(normalized.values()).issubset(set(declaration.declared_field_codes)):
                raise ValueError("Le mapping dépasse les champs déclarés pour cet import.")
            updated = await uow.csv_imports.update_mapping(
                session_id, expected_version=expected_version, mapping=normalized, now=now
            )
            if updated is None:
                raise ProspectVersionConflict(session.version)
            await uow.audit.record(
                tenant_audit_event(
                    context, AuditAction.IMPORT_MAPPING_SAVED, session_id, {"mapped_field_count": len(normalized)}
                )
            )
            await uow.commit()
            return updated


class ValidateCsvImportUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, file_store: TemporaryCsvFileStore, clock: Clock
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._file_store = file_store
        self._clock = clock

    async def execute(
        self, *, context: TenantContext, session_id: UUID, expected_version: int, has_capability: bool
    ) -> CsvImportValidation:
        _require(has_capability)
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as uow:
            session = await uow.csv_imports.get_session(session_id)
            session = _ensure_available(session, now)
            if not session.mapping:
                raise ValueError("Le mapping est obligatoire avant la validation.")
            content = await self._read(session.file_ref)
            _, rows = _parse_csv(content)
            counters = await _validate_rows(uow, rows, session.mapping)
            updated = await uow.csv_imports.record_validation(
                session_id, expected_version=expected_version, now=now, **counters
            )
            if updated is None:
                raise ProspectVersionConflict(session.version)
            await uow.audit.record(
                tenant_audit_event(context, AuditAction.IMPORT_VALIDATED, session_id, _audit_counts(counters))
            )
            await uow.commit()
        return CsvImportValidation(session=updated, **counters)

    async def _read(self, file_ref: str) -> bytes:
        content = await self._file_store.read(file_ref)
        if content is None:
            raise ValueError("Le fichier temporaire a expiré.")
        return content


class ConfirmCsvImportUseCase:
    def __init__(
        self, unit_of_work_factory: ProspectUnitOfWorkFactory, file_store: TemporaryCsvFileStore, clock: Clock
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._file_store = file_store
        self._clock = clock

    async def execute(
        self,
        *,
        context: TenantContext,
        session_id: UUID,
        expected_version: int,
        idempotency_key: str,
        has_capability: bool,
    ) -> CsvImportRunView:
        _require(has_capability)
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key est obligatoire.")
        now = self._clock.now()
        async with self._unit_of_work_factory(context) as uow:
            session = await uow.csv_imports.get_session(session_id)
            session = _ensure_available(session, now)
            fingerprint = _confirmation_fingerprint(session_id, session.content_sha256, session.mapping)
            replay = await uow.csv_imports.get_run_by_idempotency_key(idempotency_key)
            if replay is not None:
                if replay.command_fingerprint != fingerprint:
                    raise IdempotencyKeyReused
                return replay
            if session.status is not CsvImportStatus.VALIDATED:
                raise ValueError("La validation doit être confirmée avant l’import.")
            if session.version != expected_version:
                raise ProspectVersionConflict(session.version)
            declaration = await uow.import_declarations.get(session.declaration_id)
            if declaration is None:
                raise ProspectComplianceResourceNotFound
            acquisition = await uow.acquisitions.get(declaration.acquisition_record_id)
            if acquisition is None or acquisition.status is not AcquisitionStatus.APPROVED:
                raise AcquisitionNotApproved
            content = await self._read(session.file_ref)
            _, rows = _parse_csv(content)
            quarantines: list[CsvImportQuarantineView] = []
            created = duplicates = review = 0
            for line_number, row in enumerate(rows, start=2):
                state, reasons, fingerprint_value = await _classify_row(uow, row, session.mapping)
                if state is CsvImportRowState.EXACT_DUPLICATE:
                    duplicates += 1
                    continue
                if state is CsvImportRowState.REVIEW_REQUIRED:
                    review += 1
                    quarantines.append(_quarantine(line_number, ("review_required",), fingerprint_value))
                    continue
                if state is not CsvImportRowState.READY_TO_CREATE:
                    quarantines.append(_quarantine(line_number, reasons, fingerprint_value))
                    continue
                prospect = await _create_row(uow, context, acquisition, row, session.mapping, now)
                await uow.csv_imports.add_fingerprint(fingerprint=fingerprint_value, prospect_id=prospect.id, now=now)
                created += 1
            run = await uow.csv_imports.add_run(
                session_id=session_id,
                idempotency_key=idempotency_key,
                command_fingerprint=fingerprint,
                created_count=created,
                duplicate_count=duplicates,
                review_count=review,
                quarantined_count=len(quarantines),
                now=now,
            )
            await uow.csv_imports.add_quarantines(run_id=run.id, rows=tuple(quarantines), now=now)
            confirmed = await uow.csv_imports.mark_confirmed(session_id, expected_version=expected_version, now=now)
            if confirmed is None:
                raise ProspectVersionConflict(session.version)
            await uow.audit.record(
                tenant_audit_event(
                    context,
                    AuditAction.IMPORT_CONFIRMED,
                    session_id,
                    {
                        "created_count": created,
                        "duplicate_count": duplicates,
                        "review_count": review,
                        "quarantined_count": len(quarantines),
                    },
                )
            )
            await uow.commit()
        await self._file_store.delete(session.file_ref)
        return run

    async def _read(self, file_ref: str) -> bytes:
        content = await self._file_store.read(file_ref)
        if content is None:
            raise ValueError("Le fichier temporaire a expiré.")
        return content


class GetCsvImportReportUseCase:
    """Return the minimized quarantine report without exposing source values."""

    def __init__(self, unit_of_work_factory: ProspectUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self, *, context: TenantContext, run_id: UUID, has_capability: bool
    ) -> tuple[CsvImportQuarantineView, ...]:
        _require(has_capability)
        async with self._unit_of_work_factory(context) as uow:
            run = await uow.csv_imports.get_run(run_id)
            if run is None:
                raise ProspectComplianceResourceNotFound
            return await uow.csv_imports.list_quarantines(run.id, limit=500)


def _parse_csv(content: bytes) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Le fichier CSV est vide ou dépasse 10 Mio.")
    try:
        text_content = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Le fichier doit être encodé en UTF-8.") from error
    if "\x00" in text_content:
        raise ValueError("Le fichier CSV contient un caractère interdit.")
    reader = csv.DictReader(io.StringIO(text_content, newline=""))
    if not reader.fieldnames:
        raise ValueError("Le fichier CSV doit comporter une ligne d’en-têtes.")
    headers = tuple(_normalise_header(value) for value in reader.fieldnames)
    if len(headers) > MAX_COLUMNS or len(set(headers)) != len(headers) or any(not header for header in headers):
        raise ValueError("Les en-têtes CSV sont invalides.")
    rows: list[dict[str, str]] = []
    for source_row in reader:
        if len(rows) >= MAX_ROWS:
            raise ValueError("Le fichier CSV dépasse 5 000 lignes.")
        row = {headers[index]: _cell(value) for index, value in enumerate(source_row.values()) if index < len(headers)}
        rows.append(row)
    return headers, rows


def _normalise_header(value: str) -> str:
    result = " ".join(value.replace("\ufeff", "").split())
    if len(result) > 120 or any(ord(character) < 32 for character in result):
        raise ValueError("Un en-tête CSV est invalide.")
    return result


def _cell(value: str | None) -> str:
    result = " ".join((value or "").split())
    if len(result) > MAX_CELL_LENGTH or any(ord(character) < 32 for character in result):
        raise ValueError("Une cellule CSV est invalide.")
    return result


def _validate_mapping(mapping: dict[str, str]) -> dict[str, str]:
    if not mapping or len(mapping) > len(CSV_IMPORT_MAPPING_FIELDS):
        raise ValueError("Le mapping CSV est invalide.")
    normalized = {_normalise_header(column): target for column, target in mapping.items() if target}
    if set(normalized.values()) - CSV_IMPORT_MAPPING_FIELDS or len(set(normalized.values())) != len(normalized):
        raise ValueError("Les champs de mapping sont invalides.")
    if "business_name" not in normalized.values():
        raise ValueError("Le champ Nom établissement est obligatoire.")
    return normalized


async def _validate_rows(
    uow: ProspectUnitOfWork, rows: list[dict[str, str]], mapping: dict[str, str]
) -> dict[str, int]:
    ready_count = duplicate_count = review_count = quarantined_count = 0
    fingerprints_in_file: set[str] = set()
    for row in rows:
        state, _, fingerprint = await _classify_row(uow, row, mapping)
        if state is CsvImportRowState.READY_TO_CREATE and fingerprint in fingerprints_in_file:
            state = CsvImportRowState.EXACT_DUPLICATE
        elif state is CsvImportRowState.READY_TO_CREATE:
            fingerprints_in_file.add(fingerprint)
        if state is CsvImportRowState.READY_TO_CREATE:
            ready_count += 1
        elif state is CsvImportRowState.EXACT_DUPLICATE:
            duplicate_count += 1
        elif state is CsvImportRowState.REVIEW_REQUIRED:
            review_count += 1
        else:
            quarantined_count += 1
    return {
        "row_count": len(rows),
        "ready_count": ready_count,
        "duplicate_count": duplicate_count,
        "review_count": review_count,
        "quarantined_count": quarantined_count,
    }


async def _classify_row(
    uow: ProspectUnitOfWork, row: dict[str, str], mapping: dict[str, str]
) -> tuple[CsvImportRowState, tuple[str, ...], str]:
    values = {target: row.get(column, "").strip() for column, target in mapping.items()}
    fingerprint = _row_fingerprint(values)
    if not values.get("business_name"):
        return CsvImportRowState.QUARANTINED, ("business_name_missing",), fingerprint
    for field, channel_type in _CHANNEL_FIELDS.items():
        if values.get(field):
            try:
                _normalise_channel(channel_type, values[field])
            except ValueError:
                return CsvImportRowState.QUARANTINED, (f"{field}_invalid",), fingerprint
    if await uow.csv_imports.fingerprint_exists(fingerprint):
        return CsvImportRowState.EXACT_DUPLICATE, (), fingerprint
    return CsvImportRowState.READY_TO_CREATE, (), fingerprint


async def _create_row(
    uow: ProspectUnitOfWork,
    context: TenantContext,
    acquisition: AcquisitionRecordView,
    row: dict[str, str],
    mapping: dict[str, str],
    now: datetime,
) -> ProspectView:
    values = {target: row.get(column, "").strip() for column, target in mapping.items()}
    provenance = await uow.provenance.add(
        ProvenanceDraft(
            organization_id=context.organization_id,
            source_kind=ProvenanceSourceKind.CSV,
            source_label=acquisition.source_label,
            purpose=acquisition.purpose,
            territory=acquisition.territory,
            obtained_at=acquisition.obtained_at,
            provider_id=acquisition.provider_id,
            acquisition_record_id=acquisition.id,
            attested_by=context.actor_id,
        ),
        now=now,
    )
    prospect = await uow.prospects.add(
        ProspectDraft(
            organization_id=context.organization_id,
            internal_alias=values["business_name"],
            origin=ProspectOrigin.IMPORT,
            source_label=acquisition.source_label,
            acquisition_record_id=acquisition.id,
        ),
        now=now,
    )
    patch = ProspectProfilePatch(
        internal_alias=values["business_name"],
        address_line_1=values.get("business_address") or None,
    )
    updated = await uow.prospects.update(
        prospect.id,
        expected_version=prospect.version,
        patch=patch,
        profile_provenance_id=provenance.id,
        now=now,
    )
    if updated is None:
        raise ProspectVersionConflict(prospect.version)
    contact_id = None
    if values.get("contact_name"):
        contact = await uow.contacts.add(
            ContactDraft(
                organization_id=context.organization_id,
                prospect_id=prospect.id,
                display_name=values["contact_name"],
                role_label=values.get("contact_role") or None,
                provenance_id=provenance.id,
            ),
            now=now,
        )
        contact_id = contact.id
        await uow.audit.record(
            tenant_audit_event(context, AuditAction.CONTACT_CREATED, contact.id, {"prospect_id": prospect.id})
        )
    for field, channel_type in _CHANNEL_FIELDS.items():
        if not values.get(field):
            continue
        normalized = _normalise_channel(channel_type, values[field])
        channel = await uow.contact_channels.add(
            ContactChannelDraft(
                organization_id=context.organization_id,
                channel_type=channel_type,
                value=values[field],
                value_normalized=normalized,
                provenance_id=provenance.id,
                contact_id=contact_id,
                prospect_id=None if contact_id else prospect.id,
                purpose=acquisition.purpose,
                obtained_at=acquisition.obtained_at,
                created_by=context.actor_id,
            ),
            now=now,
        )
        await uow.contact_permissions.add_unknown(channel.id, organization_id=context.organization_id, now=now)
        await uow.audit.record(
            tenant_audit_event(
                context,
                AuditAction.CHANNEL_CREATED,
                channel.id,
                {"channel_type": channel_type.value, "target_type": "contact" if contact_id else "prospect"},
            )
        )
    await uow.audit.record(
        tenant_audit_event(context, AuditAction.PROVENANCE_RECORDED, provenance.id, {"source_kind": "csv"})
    )
    await uow.audit.record(tenant_audit_event(context, AuditAction.PROSPECT_CREATED, prospect.id, {"origin": "import"}))
    return prospect


def _normalise_channel(channel_type: ContactChannelType, value: str) -> str:
    collapsed = " ".join(value.split())
    if channel_type is ContactChannelType.EMAIL:
        local, separator, domain = collapsed.rpartition("@")
        if not separator or not local or not domain:
            raise ValueError("Courriel invalide.")
        normalized = f"{local.casefold()}@{domain.encode('idna').decode('ascii').casefold()}"
        if not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,253}", normalized, re.ASCII):
            raise ValueError("Courriel invalide.")
        return normalized
    if channel_type is ContactChannelType.PHONE:
        normalized = re.sub(r"[\s().-]", "", collapsed)
        if not re.fullmatch(r"\+[1-9][0-9]{7,14}", normalized):
            raise ValueError("Téléphone invalide : utilisez le format international +.")
        return normalized
    if channel_type is ContactChannelType.LINKEDIN and not re.fullmatch(
        r"https://([a-z0-9-]+\.)?linkedin\.com/.+", collapsed, re.IGNORECASE
    ):
        raise ValueError("Profil LinkedIn invalide.")
    if channel_type is ContactChannelType.FACEBOOK and not re.fullmatch(
        r"https://([a-z0-9-]+\.)?facebook\.com/.+", collapsed, re.IGNORECASE
    ):
        raise ValueError("Profil Facebook invalide.")
    return collapsed.casefold()


def _row_fingerprint(values: dict[str, str]) -> str:
    fields = ("business_name", "business_identifier", "business_address")
    material = "|".join(unicodedata.normalize("NFKC", values.get(field, "")).casefold().strip() for field in fields)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _quarantine(line_number: int, reasons: tuple[str, ...], fingerprint: str) -> CsvImportQuarantineView:
    return CsvImportQuarantineView(line_number=line_number, reason_codes=reasons, opaque_reference=fingerprint[:32])


def _ensure_available(session: CsvImportSessionView | None, now: datetime) -> CsvImportSessionView:
    if session is None:
        raise ProspectComplianceResourceNotFound
    if session.expires_at <= now or session.status in {CsvImportStatus.CONFIRMED, CsvImportStatus.EXPIRED}:
        raise ValueError("La session d’import a expiré ou a déjà été confirmée.")
    return session


def _confirmation_fingerprint(session_id: UUID, digest: str, mapping: dict[str, str]) -> str:
    payload = json.dumps(
        {"session_id": str(session_id), "digest": digest, "mapping": mapping}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _audit_counts(counters: dict[str, int]) -> dict[str, int]:
    return {key: value for key, value in counters.items() if key != "row_count"}


def _require(has_capability: bool) -> None:
    if not has_capability:
        raise InsufficientCapability
