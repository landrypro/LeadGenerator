from datetime import datetime
from typing import Protocol
from uuid import UUID

from ..models import GoogleAccessOwner, GoogleQuotaReservation, GoogleSearchQuotaPolicy


class GoogleSearchPolicyProvider(Protocol):
    async def resolve(self, owner: GoogleAccessOwner) -> GoogleSearchQuotaPolicy: ...


class GoogleSearchQuota(Protocol):
    async def reserve(
        self,
        owner: GoogleAccessOwner,
        policy: GoogleSearchQuotaPolicy,
        operation_id: UUID,
        *,
        now: datetime,
    ) -> GoogleQuotaReservation: ...
