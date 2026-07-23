from ...application.models import GooglePlaceSearchCriteria
from ...application.use_cases.search_google_places import SearchGooglePlacesOutcome
from ...domain.identity import AuthenticatedIdentity, capabilities_for
from .schemas import (
    AuthenticatedUserResponse,
    AuthenticationResponse,
    GooglePlaceSearchParameters,
    GooglePlaceSearchRequest,
    GooglePlaceSearchResponse,
    GooglePlaceSearchStats,
    GooglePlaceSummary,
    MembershipSummaryResponse,
    OrganizationSummaryResponse,
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


def to_search_criteria(request: GooglePlaceSearchRequest) -> GooglePlaceSearchCriteria:
    return GooglePlaceSearchCriteria(**request.model_dump(exclude={"requester"}))


def to_search_response(
    result: SearchGooglePlacesOutcome,
    request: GooglePlaceSearchRequest,
) -> GooglePlaceSearchResponse:
    return GooglePlaceSearchResponse(
        places=[GooglePlaceSummary.model_validate(place) for place in result.search.places],
        stats=GooglePlaceSearchStats.model_validate(result.search.stats),
        searched_at=result.search.searched_at,
        map_snapshot_token=result.map_snapshot_token,
        search_parameters=GooglePlaceSearchParameters.model_validate(request.model_dump(exclude={"requester"})),
    )
