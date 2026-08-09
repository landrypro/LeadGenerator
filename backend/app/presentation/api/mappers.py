from ...application.models import GooglePlaceSearchCriteria
from ...application.use_cases.search_google_places import SearchGooglePlacesOutcome
from ...domain.audit import AuditEventView
from ...domain.identity import AuthenticatedIdentity, capabilities_for
from ...domain.organization import MemberInvitationView, MemberView, OrganizationView
from ...domain.provisioning import ProvisioningView
from .schemas import (
    AuditActorResponse,
    AuditEventResponse,
    AuthenticatedUserResponse,
    AuthenticationResponse,
    GooglePlaceSearchParameters,
    GooglePlaceSearchRequest,
    GooglePlaceSearchResponse,
    GooglePlaceSearchStats,
    GooglePlaceSummary,
    MemberInvitationResponse,
    MemberResponse,
    MembershipSummaryResponse,
    MemberUserResponse,
    OrganizationResponse,
    OrganizationSummaryResponse,
    PlatformInvitationResponse,
    PlatformOrganizationResponse,
    ProvisioningResponse,
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
        search_parameters=GooglePlaceSearchParameters.model_validate(request.model_dump()),
    )
