from __future__ import annotations

import asyncio
import hashlib
import unicodedata
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from ...application.errors import AddressGenerationInProgress


class InMemoryGenerationGuard:
    """Adaptateur local temporaire empêchant deux recherches pour la même adresse."""

    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._active_address_hashes: set[str] = set()

    @staticmethod
    def address_key(address: str) -> str:
        decomposed = unicodedata.normalize("NFKD", address).casefold()
        without_marks = "".join(
            character for character in decomposed if not unicodedata.category(character).startswith("M")
        )
        normalized = "".join(character for character in without_marks if character.isalnum())
        if not normalized:
            normalized = unicodedata.normalize("NFKC", address).casefold().strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

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
