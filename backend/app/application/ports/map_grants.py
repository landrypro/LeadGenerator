from contextlib import AbstractAsyncContextManager
from typing import Protocol

from ..models import MapSnapshot


class MapSnapshotGrantStore(Protocol):
    async def issue(self, payload: MapSnapshot) -> str: ...

    def redeem(self, token: str) -> AbstractAsyncContextManager[MapSnapshot]: ...
