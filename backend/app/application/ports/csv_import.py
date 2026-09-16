from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol


class TemporaryCsvFileStore(Protocol):
    """Private temporary storage; implementations must never expose a public URL."""

    async def save(self, chunks: AsyncIterator[bytes]) -> tuple[str, str, int]: ...

    async def read(self, file_ref: str) -> bytes | None: ...

    async def delete(self, file_ref: str) -> None: ...

    async def cleanup_expired(self, *, max_age_seconds: int) -> int: ...
