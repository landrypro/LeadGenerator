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


class RequesterInfo(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    company_name: str = Field(min_length=2, max_length=160)
    business_address: str = Field(min_length=5, max_length=240)

    @field_validator("first_name", "company_name", "business_address")
    @classmethod
    def clean_identity_field(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Ce champ est requis.")
        return value


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
    requester: RequesterInfo


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
    search_parameters: GooglePlaceSearchParameters


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


class MapSnapshotTokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)
