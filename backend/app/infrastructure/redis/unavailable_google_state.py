from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from ...application.errors import GoogleProtectionUnavailable
from ...application.models import GoogleAccessOwner, GoogleQuotaReservation, GoogleSearchQuotaPolicy, MapSnapshot
from ...application.ports.prospect import GoogleSelectionGrantStore


class UnavailableGenerationGuard:
    """Adaptateur fermé : aucun parcours Google sans stockage partagé."""

    @asynccontextmanager
    async def hold(self, owner: GoogleAccessOwner) -> AsyncIterator[None]:
        del owner
        raise GoogleProtectionUnavailable
        yield


class UnavailableMapSnapshotGrantStore:
    async def issue(self, payload: MapSnapshot, owner: GoogleAccessOwner) -> str:
        del payload, owner
        raise GoogleProtectionUnavailable

    @asynccontextmanager
    async def redeem(self, token: str, owner: GoogleAccessOwner) -> AsyncIterator[MapSnapshot]:
        del token, owner
        raise GoogleProtectionUnavailable
        yield MapSnapshot(0, 0, 1)


class UnavailableGoogleSelectionGrantStore(GoogleSelectionGrantStore):
    async def issue(self, place_ids: tuple[str, ...], owner: GoogleAccessOwner, *, now: datetime) -> str:
        del place_ids, owner, now
        raise GoogleProtectionUnavailable

    async def resolve(self, token: str, owner: GoogleAccessOwner, *, now: datetime) -> tuple[str, ...]:
        del token, owner, now
        raise GoogleProtectionUnavailable


class UnavailableGoogleSearchQuota:
    async def reserve(
        self,
        owner: GoogleAccessOwner,
        policy: GoogleSearchQuotaPolicy,
        operation_id: object,
        *,
        now: datetime,
    ) -> GoogleQuotaReservation:
        del owner, policy, operation_id, now
        raise GoogleProtectionUnavailable
