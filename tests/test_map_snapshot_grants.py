import base64
from uuid import uuid4

import pytest

from backend.app.application.errors import (
    InvalidMapSnapshotGrant,
    MapSnapshotGrantCapacityReached,
    MapSnapshotGrantInProgress,
)
from backend.app.application.models import GoogleAccessOwner, MapSnapshot
from backend.app.infrastructure.memory import InMemoryMapSnapshotGrantStore


def snapshot_payload() -> MapSnapshot:
    return MapSnapshot(center_latitude=46.8139, center_longitude=-71.2080, radius_km=15)


def owner(*, organization_id=None) -> GoogleAccessOwner:
    return GoogleAccessOwner(uuid4(), organization_id or uuid4())


@pytest.mark.asyncio
async def test_snapshot_grant_can_only_be_redeemed_once_by_owner() -> None:
    registry = InMemoryMapSnapshotGrantStore()
    grant_owner = owner()
    token = await registry.issue(snapshot_payload(), grant_owner)

    async with registry.redeem(token, grant_owner) as payload:
        assert payload.center_latitude == 46.8139

    with pytest.raises(InvalidMapSnapshotGrant):
        async with registry.redeem(token, grant_owner):
            pass


@pytest.mark.asyncio
async def test_snapshot_grant_contains_at_least_256_bits_of_randomness() -> None:
    registry = InMemoryMapSnapshotGrantStore()
    token = await registry.issue(snapshot_payload(), owner())
    padding = "=" * (-len(token) % 4)

    assert len(base64.urlsafe_b64decode(token + padding)) >= 32


@pytest.mark.asyncio
async def test_snapshot_grant_rejects_concurrent_redemption() -> None:
    registry = InMemoryMapSnapshotGrantStore()
    grant_owner = owner()
    token = await registry.issue(snapshot_payload(), grant_owner)

    async with registry.redeem(token, grant_owner):
        with pytest.raises(MapSnapshotGrantInProgress):
            async with registry.redeem(token, grant_owner):
                pass


@pytest.mark.asyncio
async def test_snapshot_grant_is_terminal_after_failed_fetch() -> None:
    registry = InMemoryMapSnapshotGrantStore()
    grant_owner = owner()
    token = await registry.issue(snapshot_payload(), grant_owner)

    with pytest.raises(RuntimeError):
        async with registry.redeem(token, grant_owner):
            raise RuntimeError("temporary failure")

    with pytest.raises(InvalidMapSnapshotGrant):
        async with registry.redeem(token, grant_owner):
            pass


@pytest.mark.asyncio
async def test_wrong_actor_cannot_consume_owner_grant() -> None:
    registry = InMemoryMapSnapshotGrantStore()
    organization_id = uuid4()
    grant_owner = owner(organization_id=organization_id)
    same_organization = owner(organization_id=organization_id)
    other_organization = GoogleAccessOwner(grant_owner.user_id, uuid4())
    token = await registry.issue(snapshot_payload(), grant_owner)

    for intruder in (same_organization, other_organization):
        with pytest.raises(InvalidMapSnapshotGrant):
            async with registry.redeem(token, intruder):
                pass

    async with registry.redeem(token, grant_owner):
        pass


@pytest.mark.asyncio
async def test_in_progress_grant_is_never_evicted() -> None:
    registry = InMemoryMapSnapshotGrantStore(max_grants=1)
    grant_owner = owner()
    token = await registry.issue(snapshot_payload(), grant_owner)

    async with registry.redeem(token, grant_owner):
        with pytest.raises(MapSnapshotGrantCapacityReached):
            await registry.issue(snapshot_payload(), owner())


@pytest.mark.asyncio
async def test_oldest_available_grant_is_evicted_at_capacity() -> None:
    registry = InMemoryMapSnapshotGrantStore(max_grants=1)
    first_owner = owner()
    second_owner = owner()
    first = await registry.issue(snapshot_payload(), first_owner)
    second = await registry.issue(snapshot_payload(), second_owner)

    with pytest.raises(InvalidMapSnapshotGrant):
        async with registry.redeem(first, first_owner):
            pass
    async with registry.redeem(second, second_owner):
        pass


@pytest.mark.asyncio
async def test_expired_snapshot_grant_is_rejected() -> None:
    registry = InMemoryMapSnapshotGrantStore(ttl_seconds=0)
    grant_owner = owner()
    token = await registry.issue(snapshot_payload(), grant_owner)

    with pytest.raises(InvalidMapSnapshotGrant):
        async with registry.redeem(token, grant_owner):
            pass
