from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class CsvImportStatus(StrEnum):
    UPLOADED = "uploaded"
    MAPPED = "mapped"
    VALIDATED = "validated"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"


class CsvImportRowState(StrEnum):
    READY_TO_CREATE = "ready_to_create"
    EXACT_DUPLICATE = "exact_duplicate"
    REVIEW_REQUIRED = "review_required"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


CSV_IMPORT_MAPPING_FIELDS = frozenset(
    {
        "business_name",
        "business_identifier",
        "business_address",
        "contact_name",
        "contact_role",
        "email",
        "phone",
        "linkedin_profile",
        "facebook_profile",
    }
)


@dataclass(frozen=True, slots=True)
class CsvImportSessionView:
    id: UUID
    organization_id: UUID
    declaration_id: UUID
    file_ref: str
    content_sha256: str
    byte_size: int
    headers: tuple[str, ...]
    mapping: dict[str, str]
    status: CsvImportStatus
    row_count: int | None
    ready_count: int
    duplicate_count: int
    review_count: int
    quarantined_count: int
    created_at: datetime
    expires_at: datetime
    confirmed_at: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class CsvImportRunView:
    id: UUID
    organization_id: UUID
    session_id: UUID
    idempotency_key: str
    command_fingerprint: str
    created_count: int
    duplicate_count: int
    review_count: int
    quarantined_count: int
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class CsvImportQuarantineView:
    line_number: int
    reason_codes: tuple[str, ...]
    opaque_reference: str
