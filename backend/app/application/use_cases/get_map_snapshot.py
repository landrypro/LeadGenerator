from ..models import GoogleAccessContext
from ..ports.map_grants import MapSnapshotGrantStore
from ..ports.maps import MapImage, StaticMapGateway


class GetMapSnapshotUseCase:
    def __init__(self, grants: MapSnapshotGrantStore, maps: StaticMapGateway) -> None:
        self._grants = grants
        self._maps = maps

    async def execute(self, token: str, access: GoogleAccessContext) -> MapImage:
        async with self._grants.redeem(token, access.owner) as payload:
            return await self._maps.fetch(payload)
