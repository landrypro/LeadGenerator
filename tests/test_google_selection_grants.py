from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.application.errors import InvalidGoogleSelectionGrant
from backend.app.application.models import GoogleAccessOwner
from backend.app.infrastructure.memory import InMemoryGoogleSelectionGrantStore


@pytest.mark.asyncio
async def test_selection_grant_is_bound_to_owner_and_expires() -> None:
    now = datetime.now(UTC)
    store = InMemoryGoogleSelectionGrantStore(ttl_seconds=60)
    owner = GoogleAccessOwner(user_id=uuid4(), organization_id=uuid4())
    other_owner = GoogleAccessOwner(user_id=uuid4(), organization_id=owner.organization_id)

    token = await store.issue(("place-1", "place-2", "place-1"), owner, now=now)

    assert await store.resolve(token, owner, now=now + timedelta(seconds=30)) == ("place-1", "place-2")
    with pytest.raises(InvalidGoogleSelectionGrant):
        await store.resolve(token, other_owner, now=now + timedelta(seconds=30))
    with pytest.raises(InvalidGoogleSelectionGrant):
        await store.resolve(token, owner, now=now + timedelta(seconds=61))
