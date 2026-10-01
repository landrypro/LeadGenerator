from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.application.use_cases.activities import _bind_activity_channel
from backend.app.domain.activity import (
    ActivityDirection,
    ActivityType,
    ContactPermissionSnapshot,
    ProspectActivityDraft,
)
from backend.app.domain.prospect import ContactPermissionStatus


class ChannelRepository:
    def __init__(self, channel: object) -> None:
        self._channel = channel

    async def get(self, channel_id: object) -> object:
        assert channel_id == self._channel.id
        return self._channel


class PermissionRepository:
    async def get_by_channel(self, channel_id: object) -> object:
        return SimpleNamespace(channel_id=channel_id, status=ContactPermissionStatus.DO_NOT_CONTACT)


@pytest.mark.asyncio
async def test_activity_channel_binds_the_contact_and_freezes_restrictive_permission() -> None:
    prospect_id = uuid4()
    contact_id = uuid4()
    channel_id = uuid4()
    unit_of_work = SimpleNamespace(
        contact_channels=ChannelRepository(SimpleNamespace(id=channel_id, prospect_id=None, contact_id=contact_id)),
        contacts=SimpleNamespace(get=lambda _: _contact_for(prospect_id)),
        contact_permissions=PermissionRepository(),
    )
    draft = ProspectActivityDraft(
        prospect_id=prospect_id,
        activity_type=ActivityType.CALL,
        direction=ActivityDirection.OUTBOUND,
        summary="Appel déclaré",
        occurred_at=_occurred_at(),
        contact_channel_id=channel_id,
    )

    bound = await _bind_activity_channel(unit_of_work, draft)  # type: ignore[arg-type]

    assert bound.contact_id == contact_id
    assert bound.permission_snapshot is ContactPermissionSnapshot.RESTRICTED


async def _contact_for(prospect_id: object) -> object:
    return SimpleNamespace(prospect_id=prospect_id)


def _occurred_at():
    from datetime import UTC, datetime

    return datetime(2026, 9, 5, 14, tzinfo=UTC)
