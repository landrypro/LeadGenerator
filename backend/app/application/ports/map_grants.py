from contextlib import AbstractAsyncContextManager
from typing import Protocol

from ..models import GoogleAccessOwner, MapSnapshot


class MapSnapshotGrantStore(Protocol):
    async def issue(self, payload: MapSnapshot, owner: GoogleAccessOwner) -> str: ...

    def redeem(self, token: str, owner: GoogleAccessOwner) -> AbstractAsyncContextManager[MapSnapshot]: ...
