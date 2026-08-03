import asyncio
from uuid import uuid4

import pytest

from backend.app.application.models import GoogleAccessOwner
from backend.app.generation_lock import GenerationRegistry, GoogleSearchInProgress


@pytest.mark.asyncio
async def test_same_user_and_organization_cannot_search_twice_concurrently() -> None:
    registry = GenerationRegistry()
    owner = GoogleAccessOwner(uuid4(), uuid4())

    async with registry.hold(owner):
        with pytest.raises(GoogleSearchInProgress):
            async with registry.hold(owner):
                pass

    async with registry.hold(owner):
        pass


@pytest.mark.asyncio
async def test_different_users_or_organizations_can_search_concurrently() -> None:
    registry = GenerationRegistry()
    organization_id = uuid4()
    first = GoogleAccessOwner(uuid4(), organization_id)
    second = GoogleAccessOwner(uuid4(), organization_id)
    other_organization = GoogleAccessOwner(first.user_id, uuid4())

    async with registry.hold(first), registry.hold(second), registry.hold(other_organization):
        pass


@pytest.mark.asyncio
async def test_guard_releases_owner_after_failure() -> None:
    registry = GenerationRegistry()
    owner = GoogleAccessOwner(uuid4(), uuid4())

    with pytest.raises(RuntimeError):
        async with registry.hold(owner):
            raise RuntimeError("provider failed")

    async with registry.hold(owner):
        pass


@pytest.mark.asyncio
async def test_guard_releases_owner_after_cancellation() -> None:
    registry = GenerationRegistry()
    owner = GoogleAccessOwner(uuid4(), uuid4())
    acquired = asyncio.Event()

    async def cancelled_search() -> None:
        async with registry.hold(owner):
            acquired.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(cancelled_search())
    await acquired.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    async with registry.hold(owner):
        pass
