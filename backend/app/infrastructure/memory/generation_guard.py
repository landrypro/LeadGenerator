from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from ...application.errors import GoogleSearchInProgress
from ...application.models import GoogleAccessOwner


class InMemoryGenerationGuard:
    """Adaptateur mono-instance empêchant deux recherches pour le même acteur locataire."""

    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._active_owners: set[GoogleAccessOwner] = set()

    @asynccontextmanager
    async def hold(self, owner: GoogleAccessOwner) -> AsyncIterator[None]:
        async with self._guard:
            if owner in self._active_owners:
                raise GoogleSearchInProgress
            self._active_owners.add(owner)
        try:
            yield
        finally:
            async with self._guard:
                self._active_owners.discard(owner)
