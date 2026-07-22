from __future__ import annotations

import asyncio
import hashlib
import re
import unicodedata
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator


class AddressGenerationInProgress(RuntimeError):
    pass


class AddressGenerationRegistry:
    """Process-local lock preventing concurrent searches for the same address."""

    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._active_address_hashes: set[str] = set()

    @staticmethod
    def address_key(address: str) -> str:
        normalized = unicodedata.normalize("NFKD", address).encode("ascii", "ignore").decode().lower()
        normalized = re.sub(r"[^a-z0-9]+", "", normalized)
        return hashlib.sha256(normalized.encode()).hexdigest()

    @asynccontextmanager
    async def hold(self, address: str) -> AsyncIterator[None]:
        key = self.address_key(address)
        async with self._guard:
            if key in self._active_address_hashes:
                raise AddressGenerationInProgress
            self._active_address_hashes.add(key)
        try:
            yield
        finally:
            async with self._guard:
                self._active_address_hashes.discard(key)

