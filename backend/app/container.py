from dataclasses import dataclass, field

from .application.ports import AsyncResource, TenantUnitOfWorkFactory, UnitOfWorkFactory
from .application.use_cases import (
    AcceptInvitationUseCase,
    ChangeOrganizationStatusUseCase,
    CheckReadinessUseCase,
    CreateMemberInvitationUseCase,
    CreateOrganizationUseCase,
    GetCurrentSessionUseCase,
    GetMapSnapshotUseCase,
    GetOrganizationUseCase,
    ListMemberInvitationsUseCase,
    ListMembersUseCase,
    ListPlatformAuditEventsUseCase,
    ListPlatformOrganizationsUseCase,
    ListTenantAuditEventsUseCase,
    LoginUseCase,
    LogoutUseCase,
    PreviewInvitationUseCase,
    ResendInitialInvitationUseCase,
    ResendMemberInvitationUseCase,
    RevokeInitialInvitationUseCase,
    RevokeMemberInvitationUseCase,
    SearchGooglePlacesUseCase,
    SwitchOrganizationUseCase,
    UpdateMembershipUseCase,
    UpdateOrganizationUseCase,
)
from .config import Settings


@dataclass(frozen=True, slots=True)
class AppContainer:
    settings: Settings
    search_google_places: SearchGooglePlacesUseCase
    get_map_snapshot: GetMapSnapshotUseCase
    readiness: CheckReadinessUseCase = field(default_factory=CheckReadinessUseCase)
    login: LoginUseCase | None = None
    get_current_session: GetCurrentSessionUseCase | None = None
    logout: LogoutUseCase | None = None
    create_organization: CreateOrganizationUseCase | None = None
    list_platform_organizations: ListPlatformOrganizationsUseCase | None = None
    suspend_organization: ChangeOrganizationStatusUseCase | None = None
    reactivate_organization: ChangeOrganizationStatusUseCase | None = None
    list_tenant_audit_events: ListTenantAuditEventsUseCase | None = None
    list_platform_audit_events: ListPlatformAuditEventsUseCase | None = None
    resend_initial_invitation: ResendInitialInvitationUseCase | None = None
    revoke_initial_invitation: RevokeInitialInvitationUseCase | None = None
    preview_invitation: PreviewInvitationUseCase | None = None
    accept_invitation: AcceptInvitationUseCase | None = None
    get_organization: GetOrganizationUseCase | None = None
    update_organization: UpdateOrganizationUseCase | None = None
    list_members: ListMembersUseCase | None = None
    update_membership: UpdateMembershipUseCase | None = None
    list_member_invitations: ListMemberInvitationsUseCase | None = None
    create_member_invitation: CreateMemberInvitationUseCase | None = None
    resend_member_invitation: ResendMemberInvitationUseCase | None = None
    revoke_member_invitation: RevokeMemberInvitationUseCase | None = None
    switch_organization: SwitchOrganizationUseCase | None = None
    unit_of_work_factory: UnitOfWorkFactory | None = None
    tenant_unit_of_work_factory: TenantUnitOfWorkFactory | None = None
    resources: tuple[AsyncResource, ...] = ()

    async def close(self) -> None:
        errors: list[Exception] = []
        for resource in reversed(self.resources):
            try:
                await resource.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("La fermeture des ressources applicatives a échoué.", errors)
