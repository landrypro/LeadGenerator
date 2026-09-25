from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

from ..errors import StaticMapProviderError
from ..models import GoogleAccessContext
from ..ports.map_grants import MapSnapshotGrantStore
from ..ports.maps import MapImage, StaticMapGateway
from ..ports.metrics import MetricsRecorder, NullMetricsRecorder
from ..ports.usage import NullUsageStore, UsageEvent, UsageStore
from ..tenancy import TenantContext


class GetMapSnapshotUseCase:
    def __init__(
        self,
        grants: MapSnapshotGrantStore,
        maps: StaticMapGateway,
        metrics: MetricsRecorder | None = None,
        usage: UsageStore | None = None,
        operation_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._grants = grants
        self._maps = maps
        self._metrics = metrics or NullMetricsRecorder()
        self._usage = usage or NullUsageStore()
        self._operation_id_factory = operation_id_factory

    async def execute(self, token: str, access: GoogleAccessContext) -> MapImage:
        async with self._grants.redeem(token, access.owner) as payload:
            operation_id = self._operation_id_factory()
            context = TenantContext(access.user_id, access.organization_id, f"usage:{operation_id}")
            await self._usage.record(
                UsageEvent(
                    context=context,
                    membership_id=access.membership_id,
                    operation_id=operation_id,
                    usage_code="google.maps_static.request",
                    event_kind="upstream_attempted",
                    outcome="attempted",
                    occurred_at=_now(),
                )
            )
            started_at = perf_counter()
            try:
                image = await self._maps.fetch(payload)
            except StaticMapProviderError:
                self._metrics.record_google_upstream("maps_static", "failed", perf_counter() - started_at)
                await self._usage.record(
                    UsageEvent(
                        context=context,
                        membership_id=access.membership_id,
                        operation_id=operation_id,
                        usage_code="google.maps_static.request",
                        event_kind="upstream_failed",
                        outcome="failed",
                        occurred_at=_now(),
                    )
                )
                raise
            self._metrics.record_google_upstream("maps_static", "accepted", perf_counter() - started_at)
            await self._usage.record(
                UsageEvent(
                    context=context,
                    membership_id=access.membership_id,
                    operation_id=operation_id,
                    usage_code="google.maps_static.request",
                    event_kind="upstream_succeeded",
                    outcome="succeeded",
                    occurred_at=_now(),
                )
            )
            return image


def _now() -> datetime:
    return datetime.now(UTC)
