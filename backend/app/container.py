from dataclasses import dataclass, field

from .application.ports import AsyncResource, TenantUnitOfWorkFactory, UnitOfWorkFactory
from .application.use_cases import (
    AcceptInvitationUseCase,
    CheckReadinessUseCase,
    CreateOrganizationUseCase,
    GetCurrentSessionUseCase,
    GetMapSnapshotUseCase,
    ListPlatformOrganizationsUseCase,
    LoginUseCase,
    LogoutUseCase,
    PreviewInvitationUseCase,
    ResendInitialInvitationUseCase,
    RevokeInitialInvitationUseCase,
    SearchGooglePlacesUseCase,
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
    resend_initial_invitation: ResendInitialInvitationUseCase | None = None
    revoke_initial_invitation: RevokeInitialInvitationUseCase | None = None
    preview_invitation: PreviewInvitationUseCase | None = None
    accept_invitation: AcceptInvitationUseCase | None = None
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
