from time import perf_counter

from ..errors import StaticMapProviderError
from ..models import GoogleAccessContext
from ..ports.map_grants import MapSnapshotGrantStore
from ..ports.maps import MapImage, StaticMapGateway
from ..ports.metrics import MetricsRecorder, NullMetricsRecorder


class GetMapSnapshotUseCase:
    def __init__(
        self, grants: MapSnapshotGrantStore, maps: StaticMapGateway, metrics: MetricsRecorder | None = None
    ) -> None:
        self._grants = grants
        self._maps = maps
        self._metrics = metrics or NullMetricsRecorder()

    async def execute(self, token: str, access: GoogleAccessContext) -> MapImage:
        async with self._grants.redeem(token, access.owner) as payload:
            started_at = perf_counter()
            try:
                image = await self._maps.fetch(payload)
            except StaticMapProviderError:
                self._metrics.record_google_upstream("maps_static", "failed", perf_counter() - started_at)
                raise
            self._metrics.record_google_upstream("maps_static", "accepted", perf_counter() - started_at)
            return image
