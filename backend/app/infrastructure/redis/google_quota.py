from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any, cast
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import NoScriptError, RedisError

from ...application.errors import GoogleProtectionUnavailable
from ...application.models import GoogleAccessOwner, GoogleQuotaReservation, GoogleSearchQuotaPolicy
from ...application.ports.metrics import MetricsRecorder, NullMetricsRecorder

RESERVE_GOOGLE_QUOTA_SCRIPT = """
local existing = redis.call('GET', KEYS[3])
if existing then return {1, existing} end

local user_limit = tonumber(ARGV[1])
local organization_limit = tonumber(ARGV[2])
local warning_threshold = tonumber(ARGV[3])
local reset_at_epoch = tonumber(ARGV[4])
local ttl_seconds = tonumber(ARGV[5])
local policy_code = ARGV[6]
local user_used = tonumber(redis.call('GET', KEYS[1]) or '0')
local organization_used = tonumber(redis.call('GET', KEYS[2]) or '0')

local function remember(allowed, scope, next_user_used, next_organization_used, user_warning, organization_warning)
  local result = cjson.encode({
    schema_version = 1,
    allowed = allowed,
    scope = scope,
    user_used = next_user_used,
    user_remaining = math.max(user_limit - next_user_used, 0),
    organization_used = next_organization_used,
    organization_remaining = math.max(organization_limit - next_organization_used, 0),
    reset_at_epoch = reset_at_epoch,
    retry_after_seconds = ttl_seconds,
    policy_code = policy_code,
    user_warning_created = user_warning,
    organization_warning_created = organization_warning
  })
  redis.call('SET', KEYS[3], result, 'EX', ttl_seconds)
  return {1, result}
end

if user_used >= user_limit then
  return remember(false, 'user', user_used, organization_used, false, false)
end
if organization_used >= organization_limit then
  return remember(false, 'organization', user_used, organization_used, false, false)
end

user_used = redis.call('INCR', KEYS[1])
if user_used == 1 then redis.call('EXPIRE', KEYS[1], ttl_seconds) end
organization_used = redis.call('INCR', KEYS[2])
if organization_used == 1 then redis.call('EXPIRE', KEYS[2], ttl_seconds) end

local user_warning = false
local organization_warning = false
if user_limit > 0 and user_used * 100 >= user_limit * warning_threshold then
  user_warning = redis.call('SET', KEYS[4], '1', 'NX', 'EX', ttl_seconds) and true or false
end
if organization_limit > 0 and organization_used * 100 >= organization_limit * warning_threshold then
  organization_warning = redis.call('SET', KEYS[5], '1', 'NX', 'EX', ttl_seconds) and true or false
end

return remember(true, cjson.null, user_used, organization_used, user_warning, organization_warning)
"""


class RedisGoogleSearchQuota:
    """Réservation quotidienne atomique, partagée par toutes les instances API."""

    def __init__(self, client: Redis, *, environment: str, metrics: MetricsRecorder | None = None) -> None:
        self._client = client
        self._environment = environment
        self._script_sha: str | None = None
        self._metrics = metrics or NullMetricsRecorder()

    async def reserve(
        self,
        owner: GoogleAccessOwner,
        policy: GoogleSearchQuotaPolicy,
        operation_id: UUID,
        *,
        now: datetime,
    ) -> GoogleQuotaReservation:
        period, reset_at, ttl_seconds = _quota_window(now)
        effective_policy = _effective_policy(policy)
        keys = self._keys(owner, period, operation_id)
        started_at = perf_counter()
        try:
            raw = await self._execute_script(
                *keys,
                effective_policy.user_daily_limit,
                effective_policy.organization_daily_limit,
                effective_policy.warning_threshold_percent,
                int(reset_at.timestamp()),
                ttl_seconds,
                effective_policy.policy_code,
            )
        except RedisError as error:
            self._metrics.record_redis_operation("quota_reserve", "unavailable", perf_counter() - started_at)
            return await self._resolve_indeterminate(keys[2], reset_at, error)
        reservation = _reservation_from_script(raw, reset_at, effective_policy.policy_code)
        if reservation.allowed:
            self._metrics.record_redis_operation("quota_reserve", "accepted", perf_counter() - started_at)
        else:
            self._metrics.record_redis_operation("quota_reserve", "rejected", perf_counter() - started_at)
        return reservation

    async def _resolve_indeterminate(
        self,
        operation_key: str,
        reset_at: datetime,
        original_error: RedisError,
    ) -> GoogleQuotaReservation:
        try:
            raw = await self._client.get(operation_key)
        except RedisError as error:
            raise GoogleProtectionUnavailable from error
        if raw is None:
            raise GoogleProtectionUnavailable from original_error
        try:
            return _reservation_from_raw(_as_text(raw), reset_at)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise GoogleProtectionUnavailable from original_error

    async def _execute_script(self, *arguments: str | int) -> object:
        sha = self._script_sha
        if sha is None:
            sha = await self._load_script()
        try:
            return await self._client.evalsha(sha, 5, *arguments)
        except NoScriptError:
            # NOSCRIPT signifie que le script n'a pas été exécuté : un seul rejeu est sûr.
            sha = await self._load_script()
            return await self._client.evalsha(sha, 5, *arguments)

    async def _load_script(self) -> str:
        loaded = await self._client.script_load(RESERVE_GOOGLE_QUOTA_SCRIPT)
        self._script_sha = _as_text(loaded)
        return self._script_sha

    def _keys(self, owner: GoogleAccessOwner, period: str, operation_id: UUID) -> tuple[str, str, str, str, str]:
        prefix = f"prospect:{{{self._environment}}}:v1:google:{{{owner.organization_id}}}:"
        return (
            f"{prefix}quota:{period}:user:{owner.user_id}",
            f"{prefix}quota:{period}:organization",
            f"{prefix}quota:{period}:operation:{operation_id}",
            f"{prefix}warning:{period}:user:{owner.user_id}",
            f"{prefix}warning:{period}:organization",
        )


def _effective_policy(policy: GoogleSearchQuotaPolicy) -> GoogleSearchQuotaPolicy:
    if policy.enabled:
        return policy
    return GoogleSearchQuotaPolicy(
        enabled=False,
        user_daily_limit=0,
        organization_daily_limit=policy.organization_daily_limit,
        warning_threshold_percent=policy.warning_threshold_percent,
        policy_code=policy.policy_code,
    )


def _quota_window(now: datetime) -> tuple[str, datetime, int]:
    utc_now = now.astimezone(UTC) if now.tzinfo is not None else now.replace(tzinfo=UTC)
    period = utc_now.date().isoformat()
    reset_at = datetime.combine(utc_now.date() + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    ttl_seconds = max(1, math.ceil((reset_at - utc_now).total_seconds()))
    return period, reset_at, ttl_seconds


def _reservation_from_script(raw: object, reset_at: datetime, policy_code: str) -> GoogleQuotaReservation:
    result = cast(list[Any], raw)
    if len(result) != 2 or _as_int(result[0]) != 1:
        raise GoogleProtectionUnavailable("La réservation de quota Redis est invalide.")
    reservation = _reservation_from_raw(_as_text(result[1]), reset_at)
    if reservation.policy_code != policy_code:
        raise GoogleProtectionUnavailable("La politique de quota Redis est invalide.")
    return reservation


def _reservation_from_raw(raw: str, expected_reset_at: datetime) -> GoogleQuotaReservation:
    value = cast(dict[str, Any], json.loads(raw))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("Résultat de quota invalide.")
    allowed = value["allowed"]
    scope = value.get("scope")
    if not isinstance(allowed, bool) or scope not in {None, "user", "organization"}:
        raise ValueError("Résultat de quota invalide.")
    reset_at_epoch = _as_int(value["reset_at_epoch"])
    reset_at = datetime.fromtimestamp(reset_at_epoch, UTC)
    if reset_at != expected_reset_at:
        raise ValueError("Échéance de quota invalide.")
    retry_after_seconds = _as_int(value["retry_after_seconds"])
    if retry_after_seconds <= 0:
        raise ValueError("Délai de quota invalide.")
    values = {
        "allowed": allowed,
        "scope": scope,
        "user_used": _non_negative_int(value["user_used"]),
        "user_remaining": _non_negative_int(value["user_remaining"]),
        "organization_used": _non_negative_int(value["organization_used"]),
        "organization_remaining": _non_negative_int(value["organization_remaining"]),
        "reset_at": reset_at,
        "retry_after_seconds": retry_after_seconds,
        "policy_code": value["policy_code"],
        "user_warning_created": value["user_warning_created"],
        "organization_warning_created": value["organization_warning_created"],
    }
    if (
        not isinstance(values["policy_code"], str)
        or not values["policy_code"]
        or not isinstance(values["user_warning_created"], bool)
        or not isinstance(values["organization_warning_created"], bool)
        or (allowed and scope is not None)
        or (not allowed and scope is None)
    ):
        raise ValueError("Résultat de quota invalide.")
    return GoogleQuotaReservation(**values)


def _as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise ValueError("Texte Redis attendu.")


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str, bytes, bytearray)):
        raise ValueError("Entier Redis attendu.")
    return int(value)


def _non_negative_int(value: object) -> int:
    result = _as_int(value)
    if result < 0:
        raise ValueError("Entier Redis négatif.")
    return result
