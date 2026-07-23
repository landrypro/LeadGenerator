import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from ..ports.health import DependencyHealth, DependencyProbe


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    dependencies: tuple[DependencyHealth, ...]

    @property
    def is_ready(self) -> bool:
        return bool(self.dependencies) and all(dependency.is_ready for dependency in self.dependencies)


class CheckReadinessUseCase:
    def __init__(self, probes: Sequence[DependencyProbe] = ()) -> None:
        self._probes = tuple(probes)

    async def execute(self) -> ReadinessReport:
        dependencies = await asyncio.gather(*(probe.check() for probe in self._probes))
        return ReadinessReport(tuple(dependencies))
