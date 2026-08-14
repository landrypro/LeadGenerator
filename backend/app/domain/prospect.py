from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ProspectValidationError(ValueError):
    pass


class ProspectOrigin(StrEnum):
    GOOGLE_PLACE = "google_place"
    MANUAL = "manual"
    IMPORT = "import"
    CONNECTOR = "connector"
    OPEN_DATA = "open_data"


class ProspectStageCode(StrEnum):
    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    PROPOSAL_SENT = "proposal_sent"
    WON = "won"
    LOST = "lost"
    ARCHIVED = "archived"


class ContactChannelType(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"
    OTHER = "other"


class ProvenanceSourceKind(StrEnum):
    GOOGLE_MAPS = "google_maps"
    MANUAL = "manual"
    CSV = "csv"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    OPEN_DATA = "open_data"
    API = "api"
    OTHER = "other"


class ContactPermissionStatus(StrEnum):
    UNKNOWN = "unknown"
    ALLOWED = "allowed"
    DO_NOT_CONTACT = "do_not_contact"
    OPTED_OUT = "opted_out"


_GOOGLE_PLACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,254}$", re.ASCII)
_NORMALIZED_VALUE_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,512}$", re.ASCII)


@dataclass(frozen=True, slots=True)
class ProspectDraft:
    organization_id: UUID
    internal_alias: str
    origin: ProspectOrigin
    source_label: str
    google_place_id: str | None = None
    acquisition_record_id: UUID | None = None
    owner_id: UUID | None = None
    stage_code: ProspectStageCode = ProspectStageCode.NEW
    priority: int = 0
    retention_review_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_text(self.internal_alias, "internal_alias", max_length=160)
        _validate_text(self.source_label, "source_label", max_length=160)
        if not isinstance(self.origin, ProspectOrigin):
            raise ProspectValidationError("origin est invalide.")
        if not isinstance(self.stage_code, ProspectStageCode):
            raise ProspectValidationError("stage_code est invalide.")
        if self.priority < 0 or self.priority > 5:
            raise ProspectValidationError("priority doit etre comprise entre 0 et 5.")
        if self.google_place_id is not None and not _GOOGLE_PLACE_ID_PATTERN.fullmatch(self.google_place_id):
            raise ProspectValidationError("google_place_id est invalide.")


@dataclass(frozen=True, slots=True)
class ContactDraft:
    organization_id: UUID
    prospect_id: UUID
    display_name: str
    provenance_id: UUID
    role_label: str | None = None

    def __post_init__(self) -> None:
        _validate_text(self.display_name, "display_name", max_length=160)
        if self.role_label is not None:
            _validate_text(self.role_label, "role_label", max_length=120)


@dataclass(frozen=True, slots=True)
class ContactChannelDraft:
    organization_id: UUID
    channel_type: ContactChannelType
    value: str
    value_normalized: str
    provenance_id: UUID
    prospect_id: UUID | None = None
    contact_id: UUID | None = None
    purpose: str = "commercial_follow_up"
    obtained_at: datetime | None = None
    verified_at: datetime | None = None
    created_by: UUID | None = None

    def __post_init__(self) -> None:
        if (self.prospect_id is None) == (self.contact_id is None):
            raise ProspectValidationError("Un canal doit viser exactement un prospect ou un contact.")
        if not isinstance(self.channel_type, ContactChannelType):
            raise ProspectValidationError("channel_type est invalide.")
        _validate_text(self.value, "value", max_length=512)
        if not _NORMALIZED_VALUE_PATTERN.fullmatch(self.value_normalized):
            raise ProspectValidationError("value_normalized est invalide.")
        _validate_text(self.purpose, "purpose", max_length=64)


@dataclass(frozen=True, slots=True)
class ProvenanceDraft:
    organization_id: UUID
    source_kind: ProvenanceSourceKind
    source_label: str
    purpose: str
    obtained_at: datetime
    provider_id: UUID | None = None
    evidence_ref: str | None = None
    territory: str | None = None
    verified_at: datetime | None = None
    attested_by: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_kind, ProvenanceSourceKind):
            raise ProspectValidationError("source_kind est invalide.")
        _validate_text(self.source_label, "source_label", max_length=160)
        _validate_text(self.purpose, "purpose", max_length=64)
        if self.evidence_ref is not None:
            _validate_text(self.evidence_ref, "evidence_ref", max_length=256)
        if self.territory is not None:
            _validate_text(self.territory, "territory", max_length=120)


@dataclass(frozen=True, slots=True)
class ProspectView:
    id: UUID
    organization_id: UUID
    internal_alias: str
    origin: ProspectOrigin
    source_label: str
    google_place_id: str | None
    stage_code: ProspectStageCode
    priority: int
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


@dataclass(frozen=True, slots=True)
class ContactView:
    id: UUID
    organization_id: UUID
    prospect_id: UUID
    display_name: str
    role_label: str | None
    provenance_id: UUID
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


@dataclass(frozen=True, slots=True)
class ContactChannelView:
    id: UUID
    organization_id: UUID
    channel_type: ContactChannelType
    value: str
    value_normalized: str
    provenance_id: UUID
    prospect_id: UUID | None
    contact_id: UUID | None
    purpose: str
    version: int
    archived_at: datetime | None


@dataclass(frozen=True, slots=True)
class ProvenanceView:
    id: UUID
    organization_id: UUID
    source_kind: ProvenanceSourceKind
    source_label: str
    purpose: str
    obtained_at: datetime
    created_at: datetime


def ensure_channel_provenance_is_allowed(source_kind: ProvenanceSourceKind) -> None:
    if source_kind is ProvenanceSourceKind.GOOGLE_MAPS:
        raise ProspectValidationError("google_maps est interdit comme provenance de coordonnee persistante.")


def _validate_text(value: str, field_name: str, *, max_length: int) -> None:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= max_length:
        raise ProspectValidationError(f"{field_name} doit contenir entre 1 et {max_length} caracteres.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ProspectValidationError(f"{field_name} ne doit contenir aucun caractere de controle.")
