"""Bounded Stripe sandbox event replay and daily subscription observations."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.errors import BillingOperationError
from ...domain.billing import BillingErrorCode, BillingEventType
from ..billing.stripe_client import StripeSandboxClient
from ..billing.stripe_contract import normalize_stripe_event
from ..billing.webhooks import normalized_event_payload


class StripeSandboxReconciliation:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], client: StripeSandboxClient) -> None:
        self.sessions = sessions
        self.client = client

    async def run_once(self) -> bool:
        async with self.sessions.begin() as session:
            lease = await session.scalar(text("SELECT app_private.claim_stripe_sync()"))
        if lease is None:
            return False
        kind, token = lease["kind"], UUID(lease["lease_token"])
        try:
            if kind == "events":
                done, cursor = await self._events(lease)
            else:
                done, cursor = await self._subscriptions(lease)
            async with self.sessions.begin() as session:
                advanced = await session.scalar(
                    text("SELECT app_private.advance_stripe_sync(:kind,:token,:cursor,:done)"),
                    {"kind": kind, "token": token, "cursor": cursor, "done": done},
                )
            if not advanced:
                raise RuntimeError("stripe_sync_lease_lost")
        except (BillingOperationError, RuntimeError, ValueError, KeyError, TypeError) as error:
            async with self.sessions.begin() as session:
                await session.scalar(
                    text("SELECT app_private.fail_stripe_sync(:kind,:token,:code)"),
                    {
                        "kind": kind,
                        "token": token,
                        "code": "stripe_event_history_expired"
                        if isinstance(error, RuntimeError) and str(error) == "stripe_event_history_expired"
                        else "stripe_sync_unavailable",
                    },
                )
            raise
        return True

    async def _events(self, lease: dict[str, Any]) -> tuple[bool, str | None]:
        start = datetime.fromisoformat(lease["window_start"])
        end = datetime.fromisoformat(lease["window_end"])
        if start < datetime.now(UTC) - timedelta(days=29):
            raise RuntimeError("stripe_event_history_expired")
        response = await self.client.read_events(cursor=lease["cursor_reference"], starts_at=start, ends_at=end)
        events = response.get("data")
        if not isinstance(events, list) or not isinstance(response.get("has_more"), bool):
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        for raw in events:
            event = normalize_stripe_event(raw)
            normalized = normalized_event_payload(event)
            async with self.sessions.begin() as session:
                admitted = await session.scalar(
                    text(
                        "SELECT app_private.admit_stripe_sync_event(:id,:type,:object,:created,CAST(:payload AS jsonb))"
                    ),
                    {
                        "id": event.provider_event_id,
                        "type": event.event_type.value,
                        "object": event.provider_object_reference,
                        "created": event.provider_created_at,
                        "payload": json.dumps(normalized),
                    },
                )
            if not admitted:
                raise BillingOperationError(BillingErrorCode.EVENT_COLLISION)
        if response["has_more"] and not events:
            raise BillingOperationError(BillingErrorCode.STATE_UNKNOWN)
        return not response["has_more"], events[-1]["id"] if events else None

    async def _subscriptions(self, lease: dict[str, Any]) -> tuple[bool, str | None]:
        cursor = UUID(lease["cursor_reference"]) if lease["cursor_reference"] else None
        async with self.sessions.begin() as session:
            rows = await session.scalar(
                text("SELECT app_private.read_stripe_sync_subscriptions(:cursor,:until)"),
                {"cursor": cursor, "until": datetime.fromisoformat(lease["window_end"])},
            )
        if not isinstance(rows, list):
            raise RuntimeError("stripe_sync_invalid_rows")
        for row in rows:
            reference = row["reference"]
            subscription = await self.client.read_object("subscription", reference)
            # Internal observation has its own namespace and goes through the same fenced projection.
            event_id = "sync_" + hashlib.sha256(f"{lease['window_end']}:{reference}".encode()).hexdigest()[:44]
            payload = {
                "schema_version": 1,
                "provider_object_reference": reference,
                "provider_event_kind": "customer.subscription.updated",
            }
            async with self.sessions.begin() as session:
                admitted = await session.scalar(
                    text(
                        "SELECT app_private.admit_stripe_sync_event(:id,:type,:object,:created,CAST(:payload AS jsonb))"
                    ),
                    {
                        "id": event_id,
                        "type": BillingEventType.SUBSCRIPTION_SNAPSHOT.value,
                        "object": reference,
                        "created": datetime.fromtimestamp(subscription["created"], UTC),
                        "payload": json.dumps(payload),
                    },
                )
            if not admitted:
                raise BillingOperationError(BillingErrorCode.EVENT_COLLISION)
        return len(rows) < 5, str(rows[-1]["id"]) if rows else None
