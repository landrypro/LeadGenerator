from types import TracebackType
from typing import Protocol, Self

from ..tenancy import ActorContext, TenantContext


class UnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...


class TenantUnitOfWorkFactory(Protocol):
    def __call__(self, context: TenantContext) -> UnitOfWork: ...


class ActorUnitOfWorkFactory(Protocol):
    def __call__(self, context: ActorContext) -> UnitOfWork: ...
