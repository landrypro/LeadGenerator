"""Accès SQL fermé à l'inbox P53-04 via une fonction SECURITY DEFINER."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.errors import BillingOperationError
from ...application.ports.billing import BillingEventInbox, BillingWebhookAdmissionCode, NormalizedBillingEvent
from ...domain.billing import BillingErrorCode
from ..billing.webhooks import normalized_event_payload


class SqlAlchemyBillingEventInbox(BillingEventInbox):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def admit(self, *, event: NormalizedBillingEvent, payload_digest: str) -> BillingWebhookAdmissionCode:
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    text(
                        "SELECT app_private.admit_billing_webhook("
                        ":provider, :event_id, :event_type, :object_reference, :created_at, :received_at, "
                        ":payload_digest, CAST(:normalized_payload AS jsonb))"
                    ),
                    {
                        "provider": event.provider.value,
                        "event_id": event.provider_event_id,
                        "event_type": event.event_type.value,
                        "object_reference": event.provider_object_reference,
                        "created_at": event.provider_created_at,
                        "received_at": datetime.now(UTC),
                        "payload_digest": payload_digest,
                        "normalized_payload": json.dumps(normalized_event_payload(event), separators=(",", ":")),
                    },
                )
                code = result.scalar_one()["code"]
                if code == BillingWebhookAdmissionCode.ADMITTED.value:
                    persisted = await session.scalar(
                        text("SELECT app_private.record_simulated_billing_webhook_snapshot(:provider,:event_id)"),
                        {"provider": event.provider.value, "event_id": event.provider_event_id},
                    )
                    if persisted is not True:
                        raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
                await session.commit()
        except SQLAlchemyError as error:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE) from error
        try:
            return BillingWebhookAdmissionCode(code)
        except ValueError as error:
            raise BillingOperationError(BillingErrorCode.PROVIDER_UNAVAILABLE) from error
