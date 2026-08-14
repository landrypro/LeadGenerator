from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from ...application.errors import InvalidGoogleSelectionGrant, MapSnapshotGrantCapacityReached
from ...application.models import GoogleAccessOwner
from ...application.ports.prospect import GoogleSelectionGrantStore


@dataclass(frozen=True, slots=True)
class _SelectionGrant:
    place_ids: tuple[str, ...]
    owner: GoogleAccessOwner
    expires_at: datetime


class InMemoryGoogleSelectionGrantStore(GoogleSelectionGrantStore):
    """Stockage ephemere des place_id visibles apres une recherche Google."""

    def __init__(self, *, ttl_seconds: int = 600, max_grants: int = 1_000) -> None:
        if ttl_seconds <= 0 or max_grants <= 0:
            raise ValueError("La configuration des jetons de selection Google doit etre positive.")
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_grants = max_grants
        self._guard = asyncio.Lock()
        self._grants: dict[str, _SelectionGrant] = {}

    async def issue(self, place_ids: tuple[str, ...], owner: GoogleAccessOwner, *, now: datetime) -> str:
        token = secrets.token_urlsafe(32)
        unique_place_ids = tuple(dict.fromkeys(place_id for place_id in place_ids if place_id))
        async with self._guard:
            self._prune_expired(now)
            if len(self._grants) >= self._max_grants:
                if not self._grants:
                    raise MapSnapshotGrantCapacityReached
                oldest_token = min(self._grants, key=lambda key: self._grants[key].expires_at)
                self._grants.pop(oldest_token, None)
            self._grants[token] = _SelectionGrant(
                place_ids=unique_place_ids,
                owner=owner,
                expires_at=now + self._ttl,
            )
        return token

    async def resolve(self, token: str, owner: GoogleAccessOwner, *, now: datetime) -> tuple[str, ...]:
        async with self._guard:
            self._prune_expired(now)
            grant = self._grants.get(token)
            if grant is None or grant.owner != owner:
                raise InvalidGoogleSelectionGrant
            return grant.place_ids

    def _prune_expired(self, now: datetime) -> None:
        expired = [token for token, grant in self._grants.items() if grant.expires_at <= now]
        for token in expired:
            self._grants.pop(token, None)
