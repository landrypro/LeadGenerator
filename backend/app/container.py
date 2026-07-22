from dataclasses import dataclass

from .application.use_cases import ExportLeadsUseCase, GenerateLeadsUseCase, GetMapSnapshotUseCase
from .config import Settings


@dataclass(frozen=True, slots=True)
class AppContainer:
    settings: Settings
    generate_leads: GenerateLeadsUseCase
    export_leads: ExportLeadsUseCase
    get_map_snapshot: GetMapSnapshotUseCase
