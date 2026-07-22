from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import monotonic

from .models import MapSnapshotRequest


class InvalidMapSnapshotGrant(RuntimeError):
    pass


class MapSnapshotGrantInProgress(RuntimeError):
    pass


@dataclass(slots=True)
class _Grant:
    payload: MapSnapshotRequest
    expires_at: float
    in_progress: bool = False


class MapSnapshotGrantRegistry:
    """Process-local, short-lived, one-time grants for billable map requests."""

    def __init__(self, ttl_seconds: float = 300, max_grants: int = 1_000) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_grants = max_grants
        self._guard = asyncio.Lock()
        self._grants: dict[str, _Grant] = {}

    async def issue(self, payload: MapSnapshotRequest) -> str:
        token = secrets.token_urlsafe(32)
        async with self._guard:
            self._prune_expired()
            if len(self._grants) >= self._max_grants:
                oldest_token = min(self._grants, key=lambda key: self._grants[key].expires_at)
                self._grants.pop(oldest_token, None)
            self._grants[token] = _Grant(payload=payload, expires_at=monotonic() + self._ttl_seconds)
        return token

    @asynccontextmanager
    async def redeem(self, token: str) -> AsyncIterator[MapSnapshotRequest]:
        async with self._guard:
            self._prune_expired()
            grant = self._grants.get(token)
            if grant is None:
                raise InvalidMapSnapshotGrant
            if grant.in_progress:
                raise MapSnapshotGrantInProgress
            grant.in_progress = True

        try:
            yield grant.payload
        except BaseException:
            async with self._guard:
                current = self._grants.get(token)
                if current is grant:
                    current.in_progress = False
            raise
        else:
            async with self._guard:
                if self._grants.get(token) is grant:
                    self._grants.pop(token, None)

    def _prune_expired(self) -> None:
        now = monotonic()
        expired = [token for token, grant in self._grants.items() if grant.expires_at <= now]
        for token in expired:
            self._grants.pop(token, None)
