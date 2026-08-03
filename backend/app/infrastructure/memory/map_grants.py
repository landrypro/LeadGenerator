from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import monotonic

from ...application.errors import (
    InvalidMapSnapshotGrant,
    MapSnapshotGrantCapacityReached,
    MapSnapshotGrantInProgress,
)
from ...application.models import GoogleAccessOwner, MapSnapshot


@dataclass(slots=True)
class _Grant:
    payload: MapSnapshot
    owner: GoogleAccessOwner
    expires_at: float
    in_progress: bool = False


class InMemoryMapSnapshotGrantStore:
    """Adaptateur local temporaire pour les jetons facturables à usage unique."""

    def __init__(self, ttl_seconds: float = 300, max_grants: int = 1_000) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_grants = max_grants
        self._guard = asyncio.Lock()
        self._grants: dict[str, _Grant] = {}

    async def issue(self, payload: MapSnapshot, owner: GoogleAccessOwner) -> str:
        token = secrets.token_urlsafe(32)
        async with self._guard:
            self._prune_expired()
            if len(self._grants) >= self._max_grants:
                available_tokens = [key for key, grant in self._grants.items() if not grant.in_progress]
                if not available_tokens:
                    raise MapSnapshotGrantCapacityReached
                oldest_token = min(available_tokens, key=lambda key: self._grants[key].expires_at)
                self._grants.pop(oldest_token, None)
            self._grants[token] = _Grant(
                payload=payload,
                owner=owner,
                expires_at=monotonic() + self._ttl_seconds,
            )
        return token

    @asynccontextmanager
    async def redeem(self, token: str, owner: GoogleAccessOwner) -> AsyncIterator[MapSnapshot]:
        async with self._guard:
            self._prune_expired()
            grant = self._grants.get(token)
            if grant is None or grant.owner != owner:
                raise InvalidMapSnapshotGrant
            if grant.in_progress:
                raise MapSnapshotGrantInProgress
            grant.in_progress = True

        try:
            yield grant.payload
        finally:
            async with self._guard:
                if self._grants.get(token) is grant:
                    self._grants.pop(token, None)

    def _prune_expired(self) -> None:
        now = monotonic()
        expired = [token for token, grant in self._grants.items() if grant.expires_at <= now]
        for token in expired:
            self._grants.pop(token, None)
