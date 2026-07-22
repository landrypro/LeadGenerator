import pytest

from backend.app.map_snapshot_grants import (
    InvalidMapSnapshotGrant,
    MapSnapshotGrantInProgress,
    MapSnapshotGrantRegistry,
)
from backend.app.models import MapSnapshotRequest


def snapshot_payload() -> MapSnapshotRequest:
    return MapSnapshotRequest(
        center_latitude=46.8139,
        center_longitude=-71.2080,
        radius_km=15,
    )


@pytest.mark.asyncio
async def test_snapshot_grant_can_only_be_redeemed_once() -> None:
    registry = MapSnapshotGrantRegistry()
    token = await registry.issue(snapshot_payload())

    async with registry.redeem(token) as payload:
        assert payload.center_latitude == 46.8139

    with pytest.raises(InvalidMapSnapshotGrant):
        async with registry.redeem(token):
            pass


@pytest.mark.asyncio
async def test_snapshot_grant_rejects_concurrent_redemption() -> None:
    registry = MapSnapshotGrantRegistry()
    token = await registry.issue(snapshot_payload())

    async with registry.redeem(token):
        with pytest.raises(MapSnapshotGrantInProgress):
            async with registry.redeem(token):
                pass


@pytest.mark.asyncio
async def test_snapshot_grant_remains_available_after_failed_fetch() -> None:
    registry = MapSnapshotGrantRegistry()
    token = await registry.issue(snapshot_payload())

    with pytest.raises(RuntimeError):
        async with registry.redeem(token):
            raise RuntimeError("temporary failure")

    async with registry.redeem(token):
        pass


@pytest.mark.asyncio
async def test_expired_snapshot_grant_is_rejected() -> None:
    registry = MapSnapshotGrantRegistry(ttl_seconds=0)
    token = await registry.issue(snapshot_payload())

    with pytest.raises(InvalidMapSnapshotGrant):
        async with registry.redeem(token):
            pass
