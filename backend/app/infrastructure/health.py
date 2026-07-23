from backend.app.application.ports.health import DependencyHealth


class UnconfiguredDependencyProbe:
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> DependencyHealth:
        return DependencyHealth(name=self.name, state="not_configured")
