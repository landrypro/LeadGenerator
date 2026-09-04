from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(StrictCommand):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class AuthenticatedUserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    status: str
    platform_role: str | None


class OrganizationSummaryResponse(BaseModel):
    id: UUID
    name: str


class MembershipSummaryResponse(BaseModel):
    id: UUID
    organization: OrganizationSummaryResponse
    role: str


class AuthenticationResponse(BaseModel):
    user: AuthenticatedUserResponse
    active_organization: OrganizationSummaryResponse | None
    memberships: list[MembershipSummaryResponse]
    capabilities: list[str]
    csrf_token: str


class SwitchOrganizationRequest(StrictCommand):
    membership_id: UUID


class UpdateOrganizationRequest(StrictCommand):
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    locale: Literal["fr-CA", "en-CA"] | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    locale: str
    timezone: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class MemberUserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str


class MemberResponse(BaseModel):
    membership_id: UUID
    user: MemberUserResponse
    role: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class MemberPageResponse(BaseModel):
    items: list[MemberResponse]
    next_cursor: str | None


class UpdateMembershipRequest(StrictCommand):
    version: int = Field(ge=1)
    role: Literal["admin", "manager", "sales"] | None = None
    status: Literal["active", "disabled"] | None = None


class CreateMemberInvitationRequest(StrictCommand):
    email: str = Field(min_length=3, max_length=254)
    role: Literal["admin", "manager", "sales"]
    invitation_request_id: UUID


class ResendMemberInvitationRequest(StrictCommand):
    resend_request_id: UUID


class MemberInvitationResponse(BaseModel):
    id: UUID
    recipient_email: str
    role: str
    state: str
    delivery_status: str
    expires_at: datetime
    created_at: datetime
    replayed: bool


class MemberInvitationPageResponse(BaseModel):
    items: list[MemberInvitationResponse]
    next_cursor: str | None


class CreateOrganizationRequest(StrictCommand):
    name: str = Field(min_length=1, max_length=160)
    locale: str = Field(min_length=2, max_length=16)
    timezone: str = Field(min_length=1, max_length=64)
    first_administrator_email: str = Field(min_length=3, max_length=254)
    creation_request_id: UUID


class ResendInitialInvitationRequest(StrictCommand):
    resend_request_id: UUID


class ChangeOrganizationStatusRequest(StrictCommand):
    operation_id: UUID
    version: int = Field(ge=1)
    reason_code: Literal["customer_request", "billing", "security", "compliance", "administrative", "other"]
    external_reference: str | None = Field(default=None, max_length=64)


class EmptyCommand(StrictCommand):
    pass


class PlatformOrganizationResponse(BaseModel):
    id: UUID
    name: str
    locale: str
    timezone: str
    status: str
    version: int
    created_at: datetime
    activated_at: datetime | None


class PlatformInvitationResponse(BaseModel):
    id: UUID
    recipient_email: str
    role: str
    state: str
    delivery_status: str
    expires_at: datetime


class ProvisioningResponse(BaseModel):
    organization: PlatformOrganizationResponse
    first_invitation: PlatformInvitationResponse
    replayed: bool


class PlatformOrganizationPageResponse(BaseModel):
    items: list[ProvisioningResponse]
    next_cursor: str | None


class AuditActorResponse(BaseModel):
    kind: str
    id: UUID | None
    display_name: str | None


class AuditEventResponse(BaseModel):
    id: UUID
    occurred_at: datetime
    action: str
    entity_type: str
    entity_id: UUID | None
    actor: AuditActorResponse
    request_id: str
    correlation_id: str
    source: str
    metadata: dict[str, Any]
    schema_version: int


class AuditEventPageResponse(BaseModel):
    items: list[AuditEventResponse]
    next_cursor: str | None
    occurred_from: datetime
    occurred_to: datetime


class InvitationPreviewRequest(StrictCommand):
    token: str = Field(min_length=1, max_length=128)


class InvitationPreviewResponse(BaseModel):
    organization_name: str
    role: str
    expires_at: datetime
    existing_account: bool


class NewInvitationAccountRequest(StrictCommand):
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)


class AcceptInvitationRequest(StrictCommand):
    token: str = Field(min_length=1, max_length=128)
    new_account: NewInvitationAccountRequest | None = None


class GooglePlaceSearchParameters(BaseModel):
    query: str = Field(min_length=2, max_length=120)
    center_latitude: float = Field(default=46.8139, ge=-90, le=90)
    center_longitude: float = Field(default=-71.2080, ge=-180, le=180)
    radius_km: float = Field(default=15, gt=0, le=50)
    include_service_area_businesses: bool = True
    language_code: str = Field(default="fr", min_length=2, max_length=10)
    region_code: str = Field(default="CA", min_length=2, max_length=2)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Le terme de recherche est requis.")
        return value

    @field_validator("region_code")
    @classmethod
    def normalize_region(cls, value: str) -> str:
        return value.upper()


class GooglePlaceSearchRequest(GooglePlaceSearchParameters):
    model_config = ConfigDict(extra="forbid")


class GooglePlaceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    place_id: str
    name: str = ""
    address: str = ""
    google_maps_url: str = ""
    latitude: float | None = None
    longitude: float | None = None
    primary_type: str = ""
    business_status: str = ""
    service_area_business: bool = False
    distance_km: float | None = None
    radius_verified: bool = True


class GooglePlaceSearchStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    api_calls: int
    raw_results: int
    displayed_results: int
    duplicates_removed: int = 0
    outside_radius_removed: int = 0
    service_area_unverified: int = 0


class GooglePlaceSearchResponse(BaseModel):
    places: list[GooglePlaceSummary] = Field(max_length=20)
    stats: GooglePlaceSearchStats
    searched_at: datetime
    map_snapshot_token: str
    selection_token: str
    search_parameters: GooglePlaceSearchParameters


class CreateProspectRequest(StrictCommand):
    internal_alias: str = Field(min_length=1, max_length=160)


class ProspectFromGoogleItemRequest(StrictCommand):
    place_id: str = Field(min_length=1, max_length=255)
    internal_alias: str = Field(min_length=1, max_length=160)


class ProspectFromGoogleRequest(StrictCommand):
    selection_token: str = Field(min_length=32, max_length=128)
    items: list[ProspectFromGoogleItemRequest] = Field(min_length=1, max_length=20)


class ProspectResponse(BaseModel):
    id: UUID
    internal_alias: str
    origin: str
    source_label: str
    google_place_id: str | None
    stage_code: str
    priority: int
    owner_id: UUID | None
    profile_provenance_id: UUID | None
    industry_label: str | None
    segment_code: str
    size_band: str
    address_line_1: str | None
    address_line_2: str | None
    city: str | None
    region: str | None
    postal_code: str | None
    country_code: str | None
    tags: list[str]
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class ProspectPageResponse(BaseModel):
    items: list[ProspectResponse]
    next_cursor: str | None


class ProspectProfileUpdateRequest(StrictCommand):
    version: int = Field(ge=1)
    internal_alias: str | None = Field(default=None, min_length=1, max_length=160)
    industry_label: str | None = Field(default=None, min_length=1, max_length=120)
    segment_code: Literal["unspecified", "micro", "small", "medium", "enterprise"] | None = None
    size_band: Literal["unknown", "solo", "2_10", "11_50", "51_200", "201_plus"] | None = None
    address_line_1: str | None = Field(default=None, min_length=1, max_length=160)
    address_line_2: str | None = Field(default=None, min_length=1, max_length=160)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    region: str | None = Field(default=None, min_length=1, max_length=120)
    postal_code: str | None = Field(default=None, min_length=1, max_length=32)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    tags: list[str] | None = Field(default=None, max_length=20)
    owner_id: UUID | None = None
    priority: int | None = Field(default=None, ge=0, le=5)
    purpose: Literal["commercial_follow_up", "customer_relationship", "supplier_relationship"]
    territory: str = Field(min_length=2, max_length=16)


class ProspectFromGoogleItemResponse(BaseModel):
    place_id: str
    disposition: Literal["created", "existing"]
    prospect: ProspectResponse


class ProspectFromGoogleResponse(BaseModel):
    items: list[ProspectFromGoogleItemResponse]


class SourceProviderCreateRequest(StrictCommand):
    source_kind: Literal["csv", "facebook", "linkedin", "open_data", "api", "other"]
    label: str = Field(min_length=1, max_length=160)


class SourceProviderUpdateRequest(StrictCommand):
    version: int = Field(ge=1)
    label: str | None = Field(default=None, min_length=1, max_length=160)
    status: Literal["draft", "active", "suspended", "retired"] | None = None
    terms_reference: str | None = Field(default=None, min_length=1, max_length=256)
    terms_url: str | None = Field(default=None, min_length=8, max_length=256)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    allowed_territories: list[str] | None = Field(default=None, min_length=1, max_length=50)
    allowed_purposes: list[Literal["commercial_follow_up", "customer_relationship", "supplier_relationship"]] | None = (
        Field(default=None, min_length=1, max_length=10)
    )
    allowed_data_categories: (
        list[Literal["business_identity", "person_identity", "email", "phone", "social_profile"]] | None
    ) = Field(default=None, min_length=1, max_length=10)
    rights_attested: bool | None = None


class SourceProviderResponse(BaseModel):
    id: UUID
    source_kind: str
    label: str
    status: str
    terms_reference: str | None
    terms_url: str | None
    valid_from: datetime | None
    valid_until: datetime | None
    allowed_territories: list[str]
    allowed_purposes: list[str]
    allowed_data_categories: list[str]
    rights_attested_at: datetime | None
    rights_attested_by: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class SourceProviderPageResponse(BaseModel):
    items: list[SourceProviderResponse]
    next_cursor: str | None = None


class AcquisitionDeclareRequest(StrictCommand):
    source_kind: Literal["csv", "facebook", "linkedin", "open_data", "api", "other"]
    source_label: str = Field(min_length=1, max_length=160)
    provider_id: UUID
    purpose: Literal["commercial_follow_up", "customer_relationship", "supplier_relationship"]
    territory: str = Field(min_length=2, max_length=16)
    obtained_at: datetime
    data_categories: list[Literal["business_identity", "person_identity", "email", "phone", "social_profile"]] = Field(
        min_length=1,
        max_length=10,
    )
    external_reference: str | None = Field(default=None, min_length=1, max_length=128)


class AcquisitionDecisionRequest(StrictCommand):
    version: int = Field(ge=1)
    decision: Literal["approve", "reject"]
    reason_code: str | None = Field(default=None, min_length=1, max_length=64)


class AcquisitionRecordResponse(BaseModel):
    id: UUID
    source_kind: str
    source_label: str
    provider_id: UUID
    purpose: str
    territory: str
    obtained_at: datetime
    declared_by: UUID
    data_categories: list[str]
    status: str
    decision_reason_code: str | None
    external_reference: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None
    decided_by: UUID | None


class AcquisitionRecordPageResponse(BaseModel):
    items: list[AcquisitionRecordResponse]
    next_cursor: str | None = None


class ManualSourceRequest(StrictCommand):
    kind: Literal["manual"]
    purpose: Literal["commercial_follow_up", "customer_relationship", "supplier_relationship"]
    territory: str = Field(min_length=2, max_length=16)


class AcquisitionSourceRequest(StrictCommand):
    kind: Literal["acquisition"]
    acquisition_id: UUID


class ContactCreateRequest(StrictCommand):
    display_name: str = Field(min_length=1, max_length=160)
    role_label: str | None = Field(default=None, min_length=1, max_length=120)
    source: ManualSourceRequest | AcquisitionSourceRequest


class ContactResponse(BaseModel):
    id: UUID
    prospect_id: UUID
    display_name: str
    role_label: str | None
    provenance_id: UUID
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class ContactPageResponse(BaseModel):
    items: list[ContactResponse]


class ContactChannelCreateRequest(StrictCommand):
    channel_type: Literal["email", "phone", "linkedin", "facebook", "other"]
    value: str = Field(min_length=1, max_length=512)
    prospect_id: UUID | None = None
    contact_id: UUID | None = None
    source: ManualSourceRequest | AcquisitionSourceRequest


class ContactChannelResponse(BaseModel):
    id: UUID
    channel_type: str
    value: str
    value_normalized: str
    provenance_id: UUID
    prospect_id: UUID | None
    contact_id: UUID | None
    purpose: str
    version: int
    archived_at: datetime | None


class ContactPermissionResponse(BaseModel):
    id: UUID
    channel_id: UUID
    status: str
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


class ContactPermissionUpdateRequest(StrictCommand):
    version: int = Field(ge=1)
    status: Literal["allowed", "do_not_contact", "opted_out"]
    legal_basis_code: Literal["consent", "contract", "legitimate_interest", "customer_request", "other"] | None = None
    provenance_id: UUID | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=160)
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class RetentionPolicyCreateRequest(StrictCommand):
    resource_type: Literal[
        "prospect",
        "contact",
        "contact_channel",
        "acquisition_record",
        "provenance_record",
        "import_declaration",
    ]
    policy_code: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=160)
    review_after_days: int = Field(ge=1, le=36500)
    archive_after_days: int | None = Field(default=None, ge=1, le=36500)
    effective_from: datetime | None = None


class RetentionPolicyUpdateRequest(StrictCommand):
    version: int = Field(ge=1)
    policy_code: str | None = Field(default=None, min_length=1, max_length=64)
    label: str | None = Field(default=None, min_length=1, max_length=160)
    review_after_days: int | None = Field(default=None, ge=1, le=36500)
    archive_after_days: int | None = Field(default=None, ge=1, le=36500)
    effective_from: datetime | None = None


class VersionedCommand(StrictCommand):
    version: int = Field(ge=1)


class RetentionPolicyResponse(BaseModel):
    id: UUID
    resource_type: str
    policy_code: str
    label: str
    status: str
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


class RetentionPolicyPageResponse(BaseModel):
    items: list[RetentionPolicyResponse]
    next_cursor: str | None = None


class RetentionReviewResponse(BaseModel):
    resource_type: str
    resource_id: UUID
    reference_at: datetime
    review_due_at: datetime | None
    review_state: str
    policy_id: UUID | None
    policy_code: str | None
    active_hold_count: int
    archived_at: datetime | None


class RetentionReviewPageResponse(BaseModel):
    items: list[RetentionReviewResponse]
    next_cursor: str | None = None


class RetentionHoldCreateRequest(StrictCommand):
    resource_type: Literal[
        "prospect",
        "contact",
        "contact_channel",
        "acquisition_record",
        "provenance_record",
        "import_declaration",
    ]
    resource_id: UUID
    reason_code: Literal[
        "legal_request",
        "contractual_obligation",
        "investigation",
        "data_subject_request",
        "quality_review",
        "other",
    ]
    note: str | None = Field(default=None, min_length=1, max_length=500)


class RetentionHoldReleaseRequest(StrictCommand):
    version: int = Field(ge=1)
    release_reason_code: Literal["resolved", "expired", "entered_in_error", "other"]


class RetentionHoldResponse(BaseModel):
    id: UUID
    resource_type: str
    resource_id: UUID
    reason_code: str
    note: str | None
    placed_at: datetime
    placed_by: UUID | None
    released_at: datetime | None
    released_by: UUID | None
    release_reason_code: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class RetentionHoldPageResponse(BaseModel):
    items: list[RetentionHoldResponse]
    next_cursor: str | None = None


class ImportDeclarationCreateRequest(StrictCommand):
    acquisition_record_id: UUID
    declaration_label: str = Field(min_length=1, max_length=160)
    format_code: Literal["csv"]
    schema_code: Literal["prospect_contacts_v1"]
    declared_field_codes: list[
        Literal[
            "business_name",
            "business_identifier",
            "business_address",
            "contact_name",
            "contact_role",
            "email",
            "phone",
            "linkedin_profile",
            "facebook_profile",
            "notes",
        ]
    ] = Field(min_length=1, max_length=50)
    declared_data_categories: list[
        Literal["business_identity", "person_identity", "email", "phone", "social_profile"]
    ] = Field(min_length=1, max_length=10)
    estimated_row_count: int | None = Field(default=None, ge=1, le=10000000)
    declared_content_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class ImportDeclarationResponse(BaseModel):
    id: UUID
    acquisition_record_id: UUID
    declaration_label: str
    format_code: str
    schema_code: str
    declared_field_codes: list[str]
    declared_data_categories: list[str]
    estimated_row_count: int | None
    declared_content_sha256: str | None
    status: str
    decision_reason_codes: list[str]
    declared_by: UUID | None
    declared_at: datetime
    cancelled_at: datetime | None
    archived_at: datetime | None
    archived_by: UUID | None
    archive_reason_code: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class ImportDeclarationPageResponse(BaseModel):
    items: list[ImportDeclarationResponse]
    next_cursor: str | None = None


class CsvImportMappingRequest(StrictCommand):
    version: int = Field(ge=1)
    mapping: dict[
        str,
        Literal[
            "business_name",
            "business_identifier",
            "business_address",
            "contact_name",
            "contact_role",
            "email",
            "phone",
            "linkedin_profile",
            "facebook_profile",
        ],
    ] = Field(min_length=1, max_length=9)


class CsvImportVersionRequest(StrictCommand):
    version: int = Field(ge=1)


class CsvImportSessionResponse(BaseModel):
    id: UUID
    declaration_id: UUID
    content_sha256: str
    byte_size: int
    headers: list[str]
    mapping: dict[str, str]
    status: str
    row_count: int | None
    ready_count: int
    duplicate_count: int
    review_count: int
    quarantined_count: int
    created_at: datetime
    expires_at: datetime
    confirmed_at: datetime | None
    version: int


class CsvImportPreviewResponse(BaseModel):
    session: CsvImportSessionResponse
    rows: list[dict[str, str]]


class CsvImportValidationResponse(BaseModel):
    session: CsvImportSessionResponse
    row_count: int
    ready_count: int
    duplicate_count: int
    review_count: int
    quarantined_count: int


class CsvImportReportResponse(BaseModel):
    id: UUID
    session_id: UUID
    created_count: int
    duplicate_count: int
    review_count: int
    quarantined_count: int
    completed_at: datetime


class CsvImportQuarantineResponse(BaseModel):
    line_number: int
    reason_codes: list[str]
    opaque_reference: str


class ArchiveRequest(StrictCommand):
    version: int = Field(ge=1)
    archive_reason_code: Literal[
        "duplicate",
        "invalid_data",
        "no_longer_relevant",
        "relationship_ended",
        "import_cancelled",
        "other",
    ]


class ArchivedProspectResponse(BaseModel):
    prospect_id: UUID
    version: int
    contacts_archived: int
    channels_archived: int


class ArchivedContactResponse(BaseModel):
    contact_id: UUID
    version: int
    channels_archived: int


class ArchivedChannelResponse(BaseModel):
    channel_id: UUID
    version: int


# Contrat Python historique conservé uniquement pour tester la neutralisation Excel.
# Aucune route HTTP ne l'expose pendant la migration CRM.
class Lead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = ""
    address: str = ""
    phone: str = ""
    international_phone: str = ""
    website: str = ""
    google_maps_url: str = ""
    latitude: float | None = None
    longitude: float | None = None
    place_id: str = ""
    primary_type: str = ""
    business_status: str = ""
    service_area_business: bool = False
    zone_index: int
    zone_latitude: float
    zone_longitude: float
    distance_km: float | None = None
    radius_verified: bool = True
    collected_at: datetime


class ExportRequest(BaseModel):
    leads: list[Lead] = Field(max_length=1000)
    search: dict[str, Any] = Field(default_factory=dict)


class MapPoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class MapSnapshotRequest(BaseModel):
    center_latitude: float = Field(ge=-90, le=90)
    center_longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=50)
    points: list[MapPoint] = Field(default_factory=list, max_length=20)


class MapSnapshotTokenRequest(StrictCommand):
    token: str = Field(min_length=32, max_length=128)
