"""Remboursement simulé, borné et idempotent P53-07."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from ...domain.billing import BillingErrorCode
from ..errors import BillingOperationError
from ..ports.billing import BillingCommandState, BillingProviderGateway, BillingRefundRepository
from ..ports.clock import Clock
from ..tenancy import ActorContext
from .billing import BillingSessionUseCases, _digest


@dataclass(frozen=True, slots=True)
class BillingRefundOutcome:
    refund_id: UUID
    state: Literal["approved"]


class BillingRefundUseCases:
    def __init__(self, repository: BillingRefundRepository, provider: BillingProviderGateway, clock: Clock) -> None:
        self._repository = repository
        self._provider = provider
        self._clock = clock

    async def request_refund(
        self,
        *,
        context: ActorContext,
        organization_id: UUID,
        subscription_id: UUID,
        idempotency_key: str,
        approved: bool,
        session_issued_at: datetime | None,
        authorized: bool,
    ) -> BillingRefundOutcome:
        now = self._clock.now()
        BillingSessionUseCases._require_recent_authorization(authorized, session_issued_at, now)
        if not approved:
            raise BillingOperationError(BillingErrorCode.REFUND_NOT_ELIGIBLE)
        preparation = await self._repository.prepare_refund(
            context=context,
            organization_id=organization_id,
            subscription_id=subscription_id,
            command_id=uuid4(),
            idempotency_key_digest=_digest(idempotency_key),
            request_fingerprint=_fingerprint(organization_id, subscription_id, approved),
            now=now,
        )
        if preparation.state is BillingCommandState.UNKNOWN:
            raise BillingOperationError(BillingErrorCode.RECONCILIATION_REQUIRED)
        try:
            event = await self._provider.refund_first_payment(
                command=preparation.command, idempotency_key=f"refund:{preparation.command_id}"
            )
        except BillingOperationError as error:
            await self._repository.mark_refund(
                context=context,
                command_id=preparation.command_id,
                unknown=error.code is BillingErrorCode.RECONCILIATION_REQUIRED,
            )
            raise
        await self._repository.complete_refund(
            context=context, preparation=preparation, provider_event_id=event.provider_event_id
        )
        return BillingRefundOutcome(preparation.refund_id, "approved")


def _fingerprint(organization_id: UUID, subscription_id: UUID, approved: bool) -> str:
    body = json.dumps((str(organization_id), str(subscription_id), approved), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("ascii")).hexdigest()
