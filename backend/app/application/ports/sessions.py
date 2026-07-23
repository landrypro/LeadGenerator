from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...domain.identity import CreatedSession, SessionRecord


class SessionStore(Protocol):
    async def create(
        self,
        *,
        user_id: UUID,
        active_organization_id: UUID | None,
        user_version: int,
        now: datetime,
    ) -> CreatedSession: ...

    async def load_and_touch(self, token: str, now: datetime) -> SessionRecord | None: ...

    async def revoke(self, token: str) -> None: ...

    async def revoke_user(self, user_id: UUID) -> None: ...
