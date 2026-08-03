from contextlib import AbstractAsyncContextManager
from typing import Protocol

from ..models import GoogleAccessOwner


class GenerationGuard(Protocol):
    def hold(self, owner: GoogleAccessOwner) -> AbstractAsyncContextManager[None]: ...
