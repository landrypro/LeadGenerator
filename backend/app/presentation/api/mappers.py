from ...application.models import GooglePlaceSearchCriteria
from ...application.use_cases.search_google_places import SearchGooglePlacesOutcome
from ...domain.audit import AuditEventView
from ...domain.identity import AuthenticatedIdentity, capabilities_for
from ...domain.organization import MemberInvitationView, MemberView, OrganizationView
from ...domain.prospect import (
    AcquisitionRecordView,
    ContactChannelView,
    ContactPermissionView,
    ContactView,
    ImportDeclarationView,
    ProspectView,
    RetentionHoldView,
    RetentionPolicyView,
    RetentionReviewView,
    SourceProviderView,
)
from ...domain.provisioning import ProvisioningView
from .schemas import (
    AcquisitionRecordResponse,
    AuditActorResponse,
    AuditEventResponse,
    AuthenticatedUserResponse,
    AuthenticationResponse,
    ContactChannelResponse,
    ContactPermissionResponse,
    ContactResponse,
    GooglePlaceSearchParameters,
    GooglePlaceSearchRequest,
    GooglePlaceSearchResponse,
    GooglePlaceSearchStats,
    GooglePlaceSummary,
    ImportDeclarationResponse,
    MemberInvitationResponse,
    MemberResponse,
    MembershipSummaryResponse,
    MemberUserResponse,
    OrganizationResponse,
    OrganizationSummaryResponse,
    PlatformInvitationResponse,
    PlatformOrganizationResponse,
    ProspectResponse,
    ProvisioningResponse,
    RetentionHoldResponse,
    RetentionPolicyResponse,
    RetentionReviewResponse,
    SourceProviderResponse,
)


def to_audit_event_response(view: AuditEventView) -> AuditEventResponse:
    return AuditEventResponse(
        id=view.id,
        occurred_at=view.occurred_at,
        action=view.action,
        entity_type=view.entity_type,
        entity_id=view.entity_id,
        actor=AuditActorResponse(
            kind=view.actor.kind.value,
            id=view.actor.id,
            display_name=view.actor.display_name,
        ),
        request_id=view.request_id,
        correlation_id=view.correlation_id,
        source=view.source.value,
        metadata=dict(view.metadata),
        schema_version=view.schema_version,
    )


def to_organization_response(view: OrganizationView) -> OrganizationResponse:
    return OrganizationResponse(
        id=view.id,
        name=view.name,
        locale=view.locale,
        timezone=view.timezone,
        status=view.status,
        version=view.version,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def to_member_response(view: MemberView) -> MemberResponse:
    return MemberResponse(
        membership_id=view.membership_id,
        user=MemberUserResponse(id=view.user_id, email=view.email, display_name=view.display_name),
        role=view.role.value,
        status=view.status.value,
        version=view.version,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def to_member_invitation_response(view: MemberInvitationView) -> MemberInvitationResponse:
    return MemberInvitationResponse(
        id=view.id,
        recipient_email=view.recipient_email,
        role=view.role.value,
        state=view.state.value,
        delivery_status=view.delivery_status.value,
        expires_at=view.expires_at,
        created_at=view.created_at,
        replayed=view.replayed,
    )


def to_authentication_response(identity: AuthenticatedIdentity) -> AuthenticationResponse:
    active_organization = (
        OrganizationSummaryResponse(
            id=identity.active_membership.organization_id,
            name=identity.active_membership.organization_name,
        )
        if identity.active_membership is not None
        else None
    )
    memberships = [
        MembershipSummaryResponse(
            id=membership.id,
            organization=OrganizationSummaryResponse(
                id=membership.organization_id,
                name=membership.organization_name,
            ),
            role=membership.role.value,
        )
        for membership in identity.user.memberships
        if membership.is_active
    ]
    return AuthenticationResponse(
        user=AuthenticatedUserResponse(
            id=identity.user.id,
            email=identity.user.email,
            display_name=identity.user.display_name,
            status=identity.user.status.value,
            platform_role=identity.user.platform_role.value if identity.user.platform_role else None,
        ),
        active_organization=active_organization,
        memberships=memberships,
        capabilities=list(capabilities_for(identity.user, identity.active_membership)),
        csrf_token=identity.csrf_token,
    )


def to_provisioning_response(view: ProvisioningView) -> ProvisioningResponse:
    return ProvisioningResponse(
        organization=PlatformOrganizationResponse(
            id=view.organization.id,
            name=view.organization.name,
            locale=view.organization.locale,
            timezone=view.organization.timezone,
            status=view.organization.status,
            version=view.organization.version,
            created_at=view.organization.created_at,
            activated_at=view.organization.activated_at,
        ),
        first_invitation=PlatformInvitationResponse(
            id=view.first_invitation.id,
            recipient_email=view.first_invitation.recipient_email,
            role=view.first_invitation.role.value,
            state=view.first_invitation.state.value,
            delivery_status=view.first_invitation.delivery_status.value,
            expires_at=view.first_invitation.expires_at,
        ),
        replayed=view.replayed,
    )


def to_search_criteria(request: GooglePlaceSearchRequest) -> GooglePlaceSearchCriteria:
    return GooglePlaceSearchCriteria(**request.model_dump())


def to_search_response(
    result: SearchGooglePlacesOutcome,
    request: GooglePlaceSearchRequest,
) -> GooglePlaceSearchResponse:
    return GooglePlaceSearchResponse(
        places=[GooglePlaceSummary.model_validate(place) for place in result.search.places],
        stats=GooglePlaceSearchStats.model_validate(result.search.stats),
        searched_at=result.search.searched_at,
        map_snapshot_token=result.map_snapshot_token,
        selection_token=result.selection_token,
        search_parameters=GooglePlaceSearchParameters.model_validate(request.model_dump()),
    )


def to_prospect_response(view: ProspectView) -> ProspectResponse:
    return ProspectResponse(
        id=view.id,
        internal_alias=view.internal_alias,
        origin=view.origin.value,
        source_label=view.source_label,
        google_place_id=view.google_place_id,
        stage_code=view.stage_code.value,
        priority=view.priority,
        owner_id=view.owner_id,
        profile_provenance_id=view.profile_provenance_id,
        industry_label=view.industry_label,
        segment_code=view.segment_code,
        size_band=view.size_band,
        address_line_1=view.address_line_1,
        address_line_2=view.address_line_2,
        city=view.city,
        region=view.region,
        postal_code=view.postal_code,
        country_code=view.country_code,
        tags=list(view.tags),
        version=view.version,
        created_at=view.created_at,
        updated_at=view.updated_at,
        archived_at=view.archived_at,
        stage_changed_at=view.stage_changed_at,
    )


def to_source_provider_response(view: SourceProviderView) -> SourceProviderResponse:
    return SourceProviderResponse(
        id=view.id,
        source_kind=view.source_kind.value,
        label=view.label,
        status=view.status.value,
        terms_reference=view.terms_reference,
        terms_url=view.terms_url,
        valid_from=view.valid_from,
        valid_until=view.valid_until,
        allowed_territories=list(view.allowed_territories),
        allowed_purposes=list(view.allowed_purposes),
        allowed_data_categories=list(view.allowed_data_categories),
        rights_attested_at=view.rights_attested_at,
        rights_attested_by=view.rights_attested_by,
        version=view.version,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def to_acquisition_response(view: AcquisitionRecordView) -> AcquisitionRecordResponse:
    return AcquisitionRecordResponse(
        id=view.id,
        source_kind=view.source_kind.value,
        source_label=view.source_label,
        provider_id=view.provider_id,
        purpose=view.purpose,
        territory=view.territory,
        obtained_at=view.obtained_at,
        declared_by=view.declared_by,
        data_categories=list(view.data_categories),
        status=view.status.value,
        decision_reason_code=view.decision_reason_code,
        external_reference=view.external_reference,
        version=view.version,
        created_at=view.created_at,
        updated_at=view.updated_at,
        decided_at=view.decided_at,
        decided_by=view.decided_by,
    )


def to_contact_response(view: ContactView) -> ContactResponse:
    return ContactResponse(
        id=view.id,
        prospect_id=view.prospect_id,
        display_name=view.display_name,
        role_label=view.role_label,
        provenance_id=view.provenance_id,
        version=view.version,
        created_at=view.created_at,
        updated_at=view.updated_at,
        archived_at=view.archived_at,
    )


def to_contact_channel_response(view: ContactChannelView) -> ContactChannelResponse:
    return ContactChannelResponse(
        id=view.id,
        channel_type=view.channel_type.value,
        value=view.value,
        value_normalized=view.value_normalized,
        provenance_id=view.provenance_id,
        prospect_id=view.prospect_id,
        contact_id=view.contact_id,
        purpose=view.purpose,
        version=view.version,
        archived_at=view.archived_at,
    )


def to_contact_permission_response(view: ContactPermissionView) -> ContactPermissionResponse:
    return ContactPermissionResponse(
        id=view.id,
        channel_id=view.channel_id,
        status=view.status.value,
        legal_basis_code=view.legal_basis_code,
        provenance_id=view.provenance_id,
        reason=view.reason,
        decided_at=view.decided_at,
        decided_by=view.decided_by,
        valid_from=view.valid_from,
        valid_until=view.valid_until,
        version=view.version,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def to_retention_policy_response(view: RetentionPolicyView) -> RetentionPolicyResponse:
    return RetentionPolicyResponse(
        id=view.id,
        resource_type=view.resource_type.value,
        policy_code=view.policy_code,
        label=view.label,
        status=view.status.value,
        review_after_days=view.review_after_days,
        archive_after_days=view.archive_after_days,
        effective_from=view.effective_from,
        effective_until=view.effective_until,
        approved_at=view.approved_at,
        approved_by=view.approved_by,
        created_by=view.created_by,
        created_at=view.created_at,
        updated_at=view.updated_at,
        version=view.version,
    )


def to_retention_review_response(view: RetentionReviewView) -> RetentionReviewResponse:
    return RetentionReviewResponse(
        resource_type=view.resource_type.value,
        resource_id=view.resource_id,
        reference_at=view.reference_at,
        review_due_at=view.review_due_at,
        review_state=view.review_state.value,
        policy_id=view.policy_id,
        policy_code=view.policy_code,
        active_hold_count=view.active_hold_count,
        archived_at=view.archived_at,
    )


def to_retention_hold_response(view: RetentionHoldView, *, include_note: bool = True) -> RetentionHoldResponse:
    return RetentionHoldResponse(
        id=view.id,
        resource_type=view.resource_type.value,
        resource_id=view.resource_id,
        reason_code=view.reason_code.value,
        note=view.note if include_note else None,
        placed_at=view.placed_at,
        placed_by=view.placed_by,
        released_at=view.released_at,
        released_by=view.released_by,
        release_reason_code=view.release_reason_code.value if view.release_reason_code else None,
        version=view.version,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def to_import_declaration_response(view: ImportDeclarationView) -> ImportDeclarationResponse:
    return ImportDeclarationResponse(
        id=view.id,
        acquisition_record_id=view.acquisition_record_id,
        declaration_label=view.declaration_label,
        format_code=view.format_code,
        schema_code=view.schema_code,
        declared_field_codes=list(view.declared_field_codes),
        declared_data_categories=list(view.declared_data_categories),
        estimated_row_count=view.estimated_row_count,
        declared_content_sha256=view.declared_content_sha256,
        status=view.status.value,
        decision_reason_codes=list(view.decision_reason_codes),
        declared_by=view.declared_by,
        declared_at=view.declared_at,
        cancelled_at=view.cancelled_at,
        archived_at=view.archived_at,
        archived_by=view.archived_by,
        archive_reason_code=view.archive_reason_code.value if view.archive_reason_code else None,
        version=view.version,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )
