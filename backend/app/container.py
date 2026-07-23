from dataclasses import dataclass, field

from .application.ports import AsyncResource, UnitOfWorkFactory
from .application.use_cases import (
    CheckReadinessUseCase,
    GetCurrentSessionUseCase,
    GetMapSnapshotUseCase,
    LoginUseCase,
    LogoutUseCase,
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
    unit_of_work_factory: UnitOfWorkFactory | None = None
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
