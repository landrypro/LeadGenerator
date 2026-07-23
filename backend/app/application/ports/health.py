from dataclasses import dataclass
from typing import Literal, Protocol

DependencyState = Literal["ok", "unavailable", "not_configured"]


@dataclass(frozen=True, slots=True)
class DependencyHealth:
    name: str
    state: DependencyState

    @property
    def is_ready(self) -> bool:
        return self.state == "ok"


class DependencyProbe(Protocol):
    @property
    def name(self) -> str: ...

    async def check(self) -> DependencyHealth: ...
