from __future__ import annotations

import re
import unicodedata
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


class SourceProviderStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class AcquisitionStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


class QuarantineReasonCode(StrEnum):
    PROVIDER_NOT_ACTIVE = "provider_not_active"
    CONTRACT_NOT_STARTED = "contract_not_started"
    CONTRACT_EXPIRED = "contract_expired"
    SOURCE_KIND_MISMATCH = "source_kind_mismatch"
    TERRITORY_NOT_ALLOWED = "territory_not_allowed"
    PURPOSE_NOT_ALLOWED = "purpose_not_allowed"
    DATA_CATEGORY_NOT_ALLOWED = "data_category_not_allowed"
    RIGHTS_ATTESTATION_MISSING = "rights_attestation_missing"


class RetentionResourceType(StrEnum):
    PROSPECT = "prospect"
    CONTACT = "contact"
    CONTACT_CHANNEL = "contact_channel"
    ACQUISITION_RECORD = "acquisition_record"
    PROVENANCE_RECORD = "provenance_record"
    IMPORT_DECLARATION = "import_declaration"


class RetentionPolicyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class RetentionReviewState(StrEnum):
    POLICY_MISSING = "policy_missing"
    UPCOMING = "upcoming"
    DUE = "due"
    OVERDUE = "overdue"
    ON_HOLD = "on_hold"
    ARCHIVED = "archived"


class RetentionHoldReasonCode(StrEnum):
    LEGAL_REQUEST = "legal_request"
    CONTRACTUAL_OBLIGATION = "contractual_obligation"
    INVESTIGATION = "investigation"
    DATA_SUBJECT_REQUEST = "data_subject_request"
    QUALITY_REVIEW = "quality_review"
    OTHER = "other"


class RetentionHoldReleaseReasonCode(StrEnum):
    RESOLVED = "resolved"
    EXPIRED = "expired"
    ENTERED_IN_ERROR = "entered_in_error"
    OTHER = "other"


class ImportDeclarationStatus(StrEnum):
    DECLARED = "declared"
    QUARANTINED = "quarantined"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class ImportDeclarationDecisionReasonCode(StrEnum):
    CATEGORY_NOT_ACQUIRED = "category_not_acquired"
    FIELD_NOT_ALLOWED = "field_not_allowed"
    HIGH_RISK_FREE_TEXT = "high_risk_free_text"
    PROVIDER_HISTORY_INCOMPLETE = "provider_history_incomplete"


class ArchiveReasonCode(StrEnum):
    DUPLICATE = "duplicate"
    INVALID_DATA = "invalid_data"
    NO_LONGER_RELEVANT = "no_longer_relevant"
    RELATIONSHIP_ENDED = "relationship_ended"
    IMPORT_CANCELLED = "import_cancelled"
    OTHER = "other"


EXTERNAL_SOURCE_KINDS = frozenset(
    {
        ProvenanceSourceKind.CSV,
        ProvenanceSourceKind.FACEBOOK,
        ProvenanceSourceKind.LINKEDIN,
        ProvenanceSourceKind.OPEN_DATA,
        ProvenanceSourceKind.API,
        ProvenanceSourceKind.OTHER,
    }
)
SYSTEM_SOURCE_KINDS = frozenset({ProvenanceSourceKind.GOOGLE_MAPS, ProvenanceSourceKind.MANUAL})
CONTROLLED_PURPOSES = frozenset({"commercial_follow_up", "customer_relationship", "supplier_relationship"})
CONTROLLED_DATA_CATEGORIES = frozenset({"business_identity", "person_identity", "email", "phone", "social_profile"})
LEGAL_BASIS_CODES = frozenset({"consent", "contract", "legitimate_interest", "customer_request", "other"})
IMPORT_FIELD_CATEGORY_MAP = {
    "business_name": "business_identity",
    "business_identifier": "business_identity",
    "business_address": "business_identity",
    "contact_name": "person_identity",
    "contact_role": "person_identity",
    "email": "email",
    "phone": "phone",
    "linkedin_profile": "social_profile",
    "facebook_profile": "social_profile",
    "notes": "person_identity",
}
IMPORT_SCHEMA_CODES = frozenset({"prospect_contacts_v1"})


_GOOGLE_PLACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,254}$", re.ASCII)
_NORMALIZED_VALUE_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,512}$", re.ASCII)
_TERRITORY_PATTERN = re.compile(r"^[A-Z]{2}(?:-[A-Z0-9]{1,8})?$", re.ASCII)
_URL_PATTERN = re.compile(r"^https://[^\s\x00-\x1f\x7f]{1,248}$", re.ASCII)
_COUNTRY_CODE_PATTERN = re.compile(r"^[A-Z]{2}$", re.ASCII)
_SEGMENT_CODES = frozenset({"unspecified", "micro", "small", "medium", "enterprise"})
_SIZE_BANDS = frozenset({"unknown", "solo", "2_10", "11_50", "51_200", "201_plus"})


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
class ProspectProfilePatch:
    """Champs CRM modifiables, indépendants de toute donnée descriptive Google."""

    internal_alias: str | None = None
    industry_label: str | None = None
    segment_code: str | None = None
    size_band: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    country_code: str | None = None
    tags: tuple[str, ...] | None = None
    owner_id: UUID | None = None
    priority: int | None = None

    def __post_init__(self) -> None:
        if not self.changed_fields():
            raise ProspectValidationError("Au moins un champ de profil doit etre modifie.")
        for name, value, maximum in (
            ("internal_alias", self.internal_alias, 160),
            ("industry_label", self.industry_label, 120),
            ("address_line_1", self.address_line_1, 160),
            ("address_line_2", self.address_line_2, 160),
            ("city", self.city, 120),
            ("region", self.region, 120),
            ("postal_code", self.postal_code, 32),
        ):
            if value is not None:
                _validate_text(value, name, max_length=maximum)
        if self.segment_code is not None:
            _validate_controlled_choice(self.segment_code, _SEGMENT_CODES, "segment_code")
        if self.size_band is not None:
            _validate_controlled_choice(self.size_band, _SIZE_BANDS, "size_band")
        if self.country_code is not None and not _COUNTRY_CODE_PATTERN.fullmatch(self.country_code):
            raise ProspectValidationError("country_code doit etre un code ISO alpha-2 en majuscules.")
        if self.priority is not None and not 0 <= self.priority <= 5:
            raise ProspectValidationError("priority doit etre comprise entre 0 et 5.")
        if self.tags is not None:
            if len(self.tags) > 20:
                raise ProspectValidationError("tags ne peut pas contenir plus de 20 valeurs.")
            normalized = tuple(_normalize_tag(value) for value in self.tags)
            if len(set(normalized)) != len(normalized):
                raise ProspectValidationError("tags contient un doublon Unicode.")

    def changed_fields(self) -> tuple[str, ...]:
        names = (
            "internal_alias",
            "industry_label",
            "segment_code",
            "size_band",
            "address_line_1",
            "address_line_2",
            "city",
            "region",
            "postal_code",
            "country_code",
            "tags",
            "owner_id",
            "priority",
        )
        return tuple(name for name in names if getattr(self, name) is not None)

    def normalized_tags(self) -> tuple[str, ...] | None:
        return tuple(_normalize_tag(value) for value in self.tags) if self.tags is not None else None


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
    acquisition_record_id: UUID | None = None

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
class SourceProviderDraft:
    organization_id: UUID
    source_kind: ProvenanceSourceKind
    label: str
    status: SourceProviderStatus = SourceProviderStatus.DRAFT
    terms_reference: str | None = None
    terms_url: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    allowed_territories: tuple[str, ...] = ()
    allowed_purposes: tuple[str, ...] = ()
    allowed_data_categories: tuple[str, ...] = ()
    rights_attested_at: datetime | None = None
    rights_attested_by: UUID | None = None

    def __post_init__(self) -> None:
        validate_source_provider_fields(self)


@dataclass(frozen=True, slots=True)
class SourceProviderPatch:
    version: int
    label: str | None = None
    status: SourceProviderStatus | None = None
    terms_reference: str | None = None
    terms_url: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    allowed_territories: tuple[str, ...] | None = None
    allowed_purposes: tuple[str, ...] | None = None
    allowed_data_categories: tuple[str, ...] | None = None
    rights_attested: bool | None = None

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ProspectValidationError("version doit etre strictement positive.")
        if self.label is not None:
            _validate_text(self.label, "label", max_length=160)
        if self.status is not None and not isinstance(self.status, SourceProviderStatus):
            raise ProspectValidationError("status fournisseur invalide.")
        _validate_optional_provider_values(
            terms_reference=self.terms_reference,
            terms_url=self.terms_url,
            valid_from=self.valid_from,
            valid_until=self.valid_until,
            allowed_territories=self.allowed_territories,
            allowed_purposes=self.allowed_purposes,
            allowed_data_categories=self.allowed_data_categories,
        )


@dataclass(frozen=True, slots=True)
class AcquisitionDraft:
    organization_id: UUID
    source_kind: ProvenanceSourceKind
    source_label: str
    provider_id: UUID
    purpose: str
    territory: str
    obtained_at: datetime
    declared_by: UUID
    data_categories: tuple[str, ...]
    external_reference: str | None = None
    idempotency_key: str | None = None
    command_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.source_kind not in EXTERNAL_SOURCE_KINDS:
            raise ProspectValidationError("source_kind externe invalide.")
        _validate_text(self.source_label, "source_label", max_length=160)
        _validate_controlled_choice(self.purpose, CONTROLLED_PURPOSES, "purpose")
        _validate_territory(self.territory)
        _validate_categories(self.data_categories)
        if self.external_reference is not None:
            _validate_text(self.external_reference, "external_reference", max_length=128)
        if self.idempotency_key is not None:
            _validate_text(self.idempotency_key, "idempotency_key", max_length=128)
        if self.command_fingerprint is not None:
            _validate_text(self.command_fingerprint, "command_fingerprint", max_length=128)


@dataclass(frozen=True, slots=True)
class RetentionPolicyDraft:
    organization_id: UUID
    resource_type: RetentionResourceType
    policy_code: str
    label: str
    review_after_days: int
    archive_after_days: int | None = None
    effective_from: datetime | None = None
    created_by: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resource_type, RetentionResourceType):
            raise ProspectValidationError("resource_type retention invalide.")
        _validate_text(self.policy_code, "policy_code", max_length=64)
        _validate_text(self.label, "label", max_length=160)
        _validate_retention_days(self.review_after_days, self.archive_after_days)


@dataclass(frozen=True, slots=True)
class RetentionPolicyPatch:
    version: int
    policy_code: str | None = None
    label: str | None = None
    review_after_days: int | None = None
    archive_after_days: int | None = None
    effective_from: datetime | None = None

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ProspectValidationError("version doit etre strictement positive.")
        if self.policy_code is not None:
            _validate_text(self.policy_code, "policy_code", max_length=64)
        if self.label is not None:
            _validate_text(self.label, "label", max_length=160)
        if self.review_after_days is not None:
            _validate_retention_days(self.review_after_days, self.archive_after_days)


@dataclass(frozen=True, slots=True)
class RetentionPolicyView:
    id: UUID
    organization_id: UUID
    resource_type: RetentionResourceType
    policy_code: str
    label: str
    status: RetentionPolicyStatus
    review_after_days: int
    archive_after_days: int | None
    effective_from: datetime
    effective_until: datetime | None
    approved_at: datetime | None
    approved_by: UUID | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class RetentionReviewView:
    resource_type: RetentionResourceType
    resource_id: UUID
    reference_at: datetime
    review_due_at: datetime | None
    review_state: RetentionReviewState
    policy_id: UUID | None
    policy_code: str | None
    active_hold_count: int
    archived_at: datetime | None


@dataclass(frozen=True, slots=True)
class RetentionHoldDraft:
    organization_id: UUID
    resource_type: RetentionResourceType
    resource_id: UUID
    reason_code: RetentionHoldReasonCode
    note: str | None = None
    placed_by: UUID | None = None
    idempotency_key: str | None = None
    command_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resource_type, RetentionResourceType):
            raise ProspectValidationError("resource_type hold invalide.")
        if not isinstance(self.reason_code, RetentionHoldReasonCode):
            raise ProspectValidationError("reason_code hold invalide.")
        if self.note is not None:
            _validate_text(self.note, "note", max_length=500)
        if self.reason_code is RetentionHoldReasonCode.OTHER and not self.note:
            raise ProspectValidationError("note est obligatoire pour le motif other.")
        if self.idempotency_key is not None:
            _validate_text(self.idempotency_key, "idempotency_key", max_length=128)
        if self.command_fingerprint is not None:
            _validate_text(self.command_fingerprint, "command_fingerprint", max_length=128)


@dataclass(frozen=True, slots=True)
class RetentionHoldView:
    id: UUID
    organization_id: UUID
    resource_type: RetentionResourceType
    resource_id: UUID
    reason_code: RetentionHoldReasonCode
    note: str | None
    placed_at: datetime
    placed_by: UUID | None
    released_at: datetime | None
    released_by: UUID | None
    release_reason_code: RetentionHoldReleaseReasonCode | None
    version: int
    created_at: datetime
    updated_at: datetime
    command_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class ImportDeclarationDraft:
    organization_id: UUID
    acquisition_record_id: UUID
    declaration_label: str
    format_code: str
    schema_code: str
    declared_field_codes: tuple[str, ...]
    declared_data_categories: tuple[str, ...]
    estimated_row_count: int | None = None
    declared_content_sha256: str | None = None
    declared_by: UUID | None = None
    idempotency_key: str | None = None
    command_fingerprint: str | None = None

    def __post_init__(self) -> None:
        _validate_text(self.declaration_label, "declaration_label", max_length=160)
        _validate_controlled_choice(self.format_code, frozenset({"csv"}), "format_code")
        _validate_controlled_choice(self.schema_code, IMPORT_SCHEMA_CODES, "schema_code")
        _validate_controlled_values(self.declared_field_codes, frozenset(IMPORT_FIELD_CATEGORY_MAP), "field_codes")
        _validate_categories(self.declared_data_categories)
        if self.estimated_row_count is not None and not 1 <= self.estimated_row_count <= 10_000_000:
            raise ProspectValidationError("estimated_row_count est invalide.")
        if self.declared_content_sha256 is not None and not re.fullmatch(
            r"^[a-f0-9]{64}$", self.declared_content_sha256
        ):
            raise ProspectValidationError("declared_content_sha256 est invalide.")
        if self.idempotency_key is not None:
            _validate_text(self.idempotency_key, "idempotency_key", max_length=128)
        if self.command_fingerprint is not None:
            _validate_text(self.command_fingerprint, "command_fingerprint", max_length=128)


@dataclass(frozen=True, slots=True)
class ImportDeclarationView:
    id: UUID
    organization_id: UUID
    acquisition_record_id: UUID
    declaration_label: str
    format_code: str
    schema_code: str
    declared_field_codes: tuple[str, ...]
    declared_data_categories: tuple[str, ...]
    estimated_row_count: int | None
    declared_content_sha256: str | None
    status: ImportDeclarationStatus
    decision_reason_codes: tuple[str, ...]
    declared_by: UUID | None
    declared_at: datetime
    cancelled_at: datetime | None
    archived_at: datetime | None
    archived_by: UUID | None
    archive_reason_code: ArchiveReasonCode | None
    version: int
    created_at: datetime
    updated_at: datetime
    command_fingerprint: str | None = None


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
    owner_id: UUID | None = None
    profile_provenance_id: UUID | None = None
    industry_label: str | None = None
    segment_code: str = "unspecified"
    size_band: str = "unknown"
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    country_code: str | None = None
    tags: tuple[str, ...] = ()


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
    provider_id: UUID | None = None
    acquisition_record_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class SourceProviderView:
    id: UUID
    organization_id: UUID
    source_kind: ProvenanceSourceKind
    label: str
    status: SourceProviderStatus
    terms_reference: str | None
    terms_url: str | None
    valid_from: datetime | None
    valid_until: datetime | None
    allowed_territories: tuple[str, ...]
    allowed_purposes: tuple[str, ...]
    allowed_data_categories: tuple[str, ...]
    rights_attested_at: datetime | None
    rights_attested_by: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AcquisitionRecordView:
    id: UUID
    organization_id: UUID
    source_kind: ProvenanceSourceKind
    source_label: str
    provider_id: UUID
    purpose: str
    territory: str
    obtained_at: datetime
    declared_by: UUID
    data_categories: tuple[str, ...]
    status: AcquisitionStatus
    decision_reason_code: str | None
    external_reference: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None
    decided_by: UUID | None
    command_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class ContactPermissionView:
    id: UUID
    organization_id: UUID
    channel_id: UUID
    status: ContactPermissionStatus
    legal_basis_code: str | None
    provenance_id: UUID | None
    reason: str | None
    decided_at: datetime | None
    decided_by: UUID | None
    valid_from: datetime | None
    valid_until: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


def ensure_channel_provenance_is_allowed(source_kind: ProvenanceSourceKind) -> None:
    if source_kind is ProvenanceSourceKind.GOOGLE_MAPS:
        raise ProspectValidationError("google_maps est interdit comme provenance de coordonnee persistante.")


def provider_quarantine_reason(
    provider: SourceProviderView,
    *,
    source_kind: ProvenanceSourceKind,
    purpose: str,
    territory: str,
    data_categories: tuple[str, ...],
    at: datetime,
) -> QuarantineReasonCode | None:
    if provider.source_kind is not source_kind:
        return QuarantineReasonCode.SOURCE_KIND_MISMATCH
    if provider.status is not SourceProviderStatus.ACTIVE:
        return QuarantineReasonCode.PROVIDER_NOT_ACTIVE
    if provider.rights_attested_at is None or provider.rights_attested_by is None:
        return QuarantineReasonCode.RIGHTS_ATTESTATION_MISSING
    if provider.valid_from is not None and at < provider.valid_from:
        return QuarantineReasonCode.CONTRACT_NOT_STARTED
    if provider.valid_until is not None and at > provider.valid_until:
        return QuarantineReasonCode.CONTRACT_EXPIRED
    if territory not in provider.allowed_territories:
        return QuarantineReasonCode.TERRITORY_NOT_ALLOWED
    if purpose not in provider.allowed_purposes:
        return QuarantineReasonCode.PURPOSE_NOT_ALLOWED
    if any(category not in provider.allowed_data_categories for category in data_categories):
        return QuarantineReasonCode.DATA_CATEGORY_NOT_ALLOWED
    return None


def import_declaration_reason_codes(
    acquisition: AcquisitionRecordView,
    *,
    field_codes: tuple[str, ...],
    data_categories: tuple[str, ...],
) -> tuple[ImportDeclarationDecisionReasonCode, ...]:
    reasons: list[ImportDeclarationDecisionReasonCode] = []
    if acquisition.status is not AcquisitionStatus.APPROVED:
        return ()
    if any(field_code not in IMPORT_FIELD_CATEGORY_MAP for field_code in field_codes):
        reasons.append(ImportDeclarationDecisionReasonCode.FIELD_NOT_ALLOWED)
    field_categories = tuple(IMPORT_FIELD_CATEGORY_MAP[field_code] for field_code in field_codes)
    if "notes" in field_codes:
        reasons.append(ImportDeclarationDecisionReasonCode.HIGH_RISK_FREE_TEXT)
    if any(category not in acquisition.data_categories for category in data_categories + field_categories):
        reasons.append(ImportDeclarationDecisionReasonCode.CATEGORY_NOT_ACQUIRED)
    return tuple(dict.fromkeys(reasons))


def validate_source_provider_fields(provider: SourceProviderDraft) -> None:
    if provider.source_kind in SYSTEM_SOURCE_KINDS:
        raise ProspectValidationError("source_kind fournisseur invalide.")
    if not isinstance(provider.status, SourceProviderStatus):
        raise ProspectValidationError("status fournisseur invalide.")
    _validate_text(provider.label, "label", max_length=160)
    _validate_optional_provider_values(
        terms_reference=provider.terms_reference,
        terms_url=provider.terms_url,
        valid_from=provider.valid_from,
        valid_until=provider.valid_until,
        allowed_territories=provider.allowed_territories,
        allowed_purposes=provider.allowed_purposes,
        allowed_data_categories=provider.allowed_data_categories,
    )


def _validate_text(value: str, field_name: str, *, max_length: int) -> None:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= max_length:
        raise ProspectValidationError(f"{field_name} doit contenir entre 1 et {max_length} caracteres.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ProspectValidationError(f"{field_name} ne doit contenir aucun caractere de controle.")


def _normalize_tag(value: str) -> str:
    if not isinstance(value, str):
        raise ProspectValidationError("tags contient une valeur invalide.")
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    _validate_text(normalized, "tag", max_length=64)
    return normalized


def _validate_optional_provider_values(
    *,
    terms_reference: str | None,
    terms_url: str | None,
    valid_from: datetime | None,
    valid_until: datetime | None,
    allowed_territories: tuple[str, ...] | None,
    allowed_purposes: tuple[str, ...] | None,
    allowed_data_categories: tuple[str, ...] | None,
) -> None:
    if terms_reference is not None:
        _validate_text(terms_reference, "terms_reference", max_length=256)
    if terms_url is not None and not _URL_PATTERN.fullmatch(terms_url):
        raise ProspectValidationError("terms_url doit etre une URL HTTPS.")
    if valid_from is not None and valid_until is not None and valid_until < valid_from:
        raise ProspectValidationError("valid_until doit etre posterieure a valid_from.")
    if allowed_territories is not None:
        for territory in allowed_territories:
            _validate_territory(territory)
        if len(set(allowed_territories)) != len(allowed_territories):
            raise ProspectValidationError("allowed_territories contient un doublon.")
    if allowed_purposes:
        _validate_controlled_values(allowed_purposes, CONTROLLED_PURPOSES, "allowed_purposes")
    if allowed_data_categories:
        _validate_categories(allowed_data_categories)


def _validate_controlled_values(values: tuple[str, ...], allowed: frozenset[str], field_name: str) -> None:
    if not values:
        raise ProspectValidationError(f"{field_name} doit contenir au moins une valeur.")
    if any(value not in allowed for value in values):
        raise ProspectValidationError(f"{field_name} contient une valeur invalide.")
    if len(set(values)) != len(values):
        raise ProspectValidationError(f"{field_name} contient un doublon.")


def _validate_controlled_choice(value: str, allowed: frozenset[str], field_name: str) -> None:
    if value not in allowed:
        raise ProspectValidationError(f"{field_name} contient une valeur invalide.")


def _validate_categories(values: tuple[str, ...]) -> None:
    _validate_controlled_values(values, CONTROLLED_DATA_CATEGORIES, "data_categories")


def _validate_territory(value: str) -> None:
    if not _TERRITORY_PATTERN.fullmatch(value):
        raise ProspectValidationError("territory est invalide.")


def _validate_retention_days(review_after_days: int, archive_after_days: int | None) -> None:
    if not 1 <= review_after_days <= 36_500:
        raise ProspectValidationError("review_after_days est invalide.")
    if archive_after_days is not None and not review_after_days <= archive_after_days <= 36_500:
        raise ProspectValidationError("archive_after_days est invalide.")
