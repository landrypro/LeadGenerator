from contextlib import AbstractAsyncContextManager
from typing import Protocol


class GenerationGuard(Protocol):
    def hold(self, address: str) -> AbstractAsyncContextManager[None]: ...
