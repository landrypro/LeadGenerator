"""Boucle P53-05 de projection durable de l'inbox Billing.

Le rôle worker ne lit jamais les tables Billing globales directement : les trois
fonctions SECURITY DEFINER limitent ses opérations au claim, à l'effet atomique
et à la reprise bornée.
"""

from __future__ import annotations

import json
import logging
from typing import cast

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

LOGGER = logging.getLogger(__name__)


class BillingProjectionWorker:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def run_once(self) -> bool:
        async with self._sessions.begin() as session:
            inbox_id = await session.scalar(text("SELECT app_private.claim_billing_event()"))
        if inbox_id is None:
            return False
        try:
            async with self._sessions.begin() as session:
                provider = await session.scalar(
                    text("SELECT app_private.billing_event_provider(:inbox_id)"), {"inbox_id": inbox_id}
                )
                statement = (
                    "SELECT app_private.project_stripe_sandbox_subscription_event(:inbox_id)"
                    if provider == "stripe"
                    else "SELECT app_private.project_billing_event(:inbox_id)"
                )
                result = await session.scalar(text(statement), {"inbox_id": inbox_id})
            result_code = _result_code(result)
            if result_code not in {"processed", "transitioned", "ignored", "lost_claim"}:
                raise RuntimeError("billing_projection_invalid_result")
        except (RuntimeError, SQLAlchemyError) as error:
            LOGGER.warning("billing_projection_failed error_type=%s", type(error).__name__)
            async with self._sessions.begin() as session:
                await session.scalar(
                    text("SELECT app_private.fail_billing_event_projection(:inbox_id)"), {"inbox_id": inbox_id}
                )
        return True

    async def run_lifecycle_once(self) -> bool:
        """Applique une seule échéance de grâce durable, sans lecture directe des tables."""

        async with self._sessions.begin() as session:
            subscription_id = await session.scalar(text("SELECT app_private.claim_billing_lifecycle_timer()"))
        if subscription_id is None:
            return False
        async with self._sessions.begin() as session:
            result = await session.scalar(
                text("SELECT app_private.project_billing_lifecycle_timer(:subscription_id)"),
                {"subscription_id": subscription_id},
            )
        if result not in {"grace_started", "suspended", "unchanged", "lost_claim"}:
            raise RuntimeError("billing_lifecycle_invalid_result")
        return True


def _result_code(value: object) -> str:
    decoded = json.loads(value) if isinstance(value, str) else value
    if not isinstance(decoded, dict) or not isinstance(decoded.get("result_code"), str):
        raise RuntimeError("billing_projection_invalid_result")
    return cast(str, decoded["result_code"])
