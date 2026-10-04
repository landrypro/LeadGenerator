from __future__ import annotations

import hashlib
import hmac
import math
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from ...application.ports.assistant import (
    AssistantProtectionUnavailable,
    AssistantQuotaReservation,
)
from ...application.ports.metrics import AssistantProtectionScope, MetricsRecorder, NullMetricsRecorder

RESERVE_SCRIPT = """
if redis.call('EXISTS', KEYS[4]) == 1 then return {0, 'circuit', redis.call('TTL', KEYS[4])} end
local user_used = tonumber(redis.call('GET', KEYS[1]) or '0')
local org_used = tonumber(redis.call('GET', KEYS[2]) or '0')
local budget_used = tonumber(redis.call('GET', KEYS[3]) or '0')
if user_used >= tonumber(ARGV[1]) then return {0, 'user', redis.call('TTL', KEYS[1])} end
if org_used >= tonumber(ARGV[2]) then return {0, 'organization', redis.call('TTL', KEYS[2])} end
if budget_used + tonumber(ARGV[4]) > tonumber(ARGV[3]) then return {0, 'budget', redis.call('TTL', KEYS[3])} end
user_used = redis.call('INCR', KEYS[1])
if user_used == 1 then redis.call('EXPIRE', KEYS[1], tonumber(ARGV[5])) end
org_used = redis.call('INCR', KEYS[2])
if org_used == 1 then redis.call('EXPIRE', KEYS[2], tonumber(ARGV[6])) end
budget_used = redis.call('INCRBY', KEYS[3], tonumber(ARGV[4]))
if budget_used == tonumber(ARGV[4]) then redis.call('EXPIRE', KEYS[3], tonumber(ARGV[7])) end
return {1, '', 0}
"""


class RedisAssistantProtection:
    """Limites atomiques IMP-A5, pseudonymisées et fermées en cas de panne."""

    def __init__(
        self,
        client: Redis,
        *,
        environment: str,
        hmac_key: str,
        user_window_seconds: int = 60,
        user_limit: int = 10,
        organization_window_seconds: int = 3_600,
        organization_limit: int = 100,
        daily_budget: int = 500,
        call_cost: int = 1,
        circuit_failure_limit: int = 5,
        circuit_window_seconds: int = 60,
        circuit_open_seconds: int = 60,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._client = client
        self._prefix = f"prospect:{{{environment}}}:v1:assistant"
        self._hmac_key = hmac_key.encode("utf-8")
        self._user_window_seconds = user_window_seconds
        self._user_limit = user_limit
        self._organization_window_seconds = organization_window_seconds
        self._organization_limit = organization_limit
        self._daily_budget = daily_budget
        self._call_cost = call_cost
        self._circuit_failure_limit = circuit_failure_limit
        self._circuit_window_seconds = circuit_window_seconds
        self._circuit_open_seconds = circuit_open_seconds
        self._metrics = metrics or NullMetricsRecorder()

    async def reserve(self, *, organization_id: UUID, user_id: UUID, now: datetime) -> AssistantQuotaReservation:
        utc_now = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)
        user_period = int(utc_now.timestamp()) // self._user_window_seconds
        org_period = int(utc_now.timestamp()) // self._organization_window_seconds
        day = utc_now.date().isoformat()
        reset_at = datetime.combine(utc_now.date() + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        budget_ttl = max(1, math.ceil((reset_at - utc_now).total_seconds()))
        org_key = self._digest(str(organization_id))
        user_key = self._digest(f"{organization_id}:{user_id}")
        keys = (
            f"{self._prefix}:user:{user_key}:{user_period}",
            f"{self._prefix}:organization:{org_key}:{org_period}",
            f"{self._prefix}:budget:{day}",
            f"{self._prefix}:circuit:open",
        )
        try:
            raw = await self._client.eval(
                RESERVE_SCRIPT,
                4,
                *keys,
                self._user_limit,
                self._organization_limit,
                self._daily_budget,
                self._call_cost,
                self._user_window_seconds,
                self._organization_window_seconds,
                budget_ttl,
            )
            values = list(raw)
            allowed = int(values[0]) == 1
            scope = _text(values[1]) or None
            retry_after = max(0, int(values[2]))
        except (RedisError, TypeError, ValueError, IndexError) as error:
            self._metrics.record_assistant_protection("circuit", "unavailable")
            raise AssistantProtectionUnavailable from error
        if scope not in {None, "user", "organization", "budget", "circuit"}:
            raise AssistantProtectionUnavailable
        typed_scope = cast(AssistantProtectionScope | None, scope)
        if allowed:
            for accepted_scope in ("user", "organization", "budget", "circuit"):
                self._metrics.record_assistant_protection(accepted_scope, "accepted")
        else:
            assert typed_scope is not None
            self._metrics.record_assistant_protection(typed_scope, "rejected")
        return AssistantQuotaReservation(allowed=allowed, scope=typed_scope, retry_after_seconds=retry_after)

    async def record_provider_success(self) -> None:
        try:
            await self._client.delete(f"{self._prefix}:circuit:failures")
        except RedisError:
            return None

    async def record_provider_failure(self) -> None:
        failure_key = f"{self._prefix}:circuit:failures"
        try:
            failures = int(await self._client.incr(failure_key))
            if failures == 1:
                await self._client.expire(failure_key, self._circuit_window_seconds)
            if failures >= self._circuit_failure_limit:
                await self._client.set(f"{self._prefix}:circuit:open", "1", ex=self._circuit_open_seconds)
        except RedisError:
            return None

    def _digest(self, value: str) -> str:
        return hmac.new(self._hmac_key, value.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def _text(value: object) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)
