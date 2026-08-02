from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID


class CursorCodec(Protocol):
    def encode(self, created_at: datetime, item_id: UUID) -> str: ...

    def decode(self, cursor: str | None) -> tuple[datetime | None, UUID | None]: ...
