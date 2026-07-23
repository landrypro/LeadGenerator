from __future__ import annotations

import hashlib
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from ...application.errors import AuthenticationServiceUnavailable
from ...application.ports import LoginLimitStatus

REGISTER_FAILURE_SCRIPT = """
local pair_count = redis.call('INCR', KEYS[1])
if pair_count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ip_count = redis.call('INCR', KEYS[2])
if ip_count == 1 then redis.call('EXPIRE', KEYS[2], ARGV[1]) end
local blocked = pair_count >= tonumber(ARGV[2]) or ip_count >= tonumber(ARGV[3])
local retry = math.max(redis.call('TTL', KEYS[1]), redis.call('TTL', KEYS[2]), 1)
return {blocked and 1 or 0, retry}
"""


class RedisLoginRateLimiter:
    def __init__(
        self,
        client: Redis,
        *,
        environment: str,
        window_seconds: int,
        pair_limit: int,
        address_limit: int,
    ) -> None:
        self._client = client
        self._window_seconds = window_seconds
        self._pair_limit = pair_limit
        self._address_limit = address_limit
        self._prefix = f"prospect:{environment}:login-limit:"

    async def check(self, *, client_address: str, email_dimension: str) -> LoginLimitStatus:
        pair_key, address_key = self._keys(client_address, email_dimension)
        try:
            values = await self._client.mget(pair_key, address_key)
            pair_count = int(values[0] or 0)
            address_count = int(values[1] or 0)
            blocked = pair_count >= self._pair_limit or address_count >= self._address_limit
            if not blocked:
                return LoginLimitStatus(blocked=False)
            time_to_live = await self._client.ttl(pair_key if pair_count >= self._pair_limit else address_key)
        except RedisError as error:
            raise AuthenticationServiceUnavailable from error
        return LoginLimitStatus(blocked=True, retry_after_seconds=max(1, int(time_to_live)))

    async def record_failure(self, *, client_address: str, email_dimension: str) -> LoginLimitStatus:
        pair_key, address_key = self._keys(client_address, email_dimension)
        try:
            raw = await self._client.eval(
                REGISTER_FAILURE_SCRIPT,
                2,
                pair_key,
                address_key,
                self._window_seconds,
                self._pair_limit,
                self._address_limit,
            )
        except RedisError as error:
            raise AuthenticationServiceUnavailable from error
        result = cast(list[int], raw)
        return LoginLimitStatus(blocked=bool(result[0]), retry_after_seconds=max(1, int(result[1])))

    async def reset_after_success(self, *, client_address: str, email_dimension: str) -> None:
        pair_key, _ = self._keys(client_address, email_dimension)
        try:
            await self._client.delete(pair_key)
        except RedisError as error:
            raise AuthenticationServiceUnavailable from error

    def _keys(self, client_address: str, email_dimension: str) -> tuple[str, str]:
        address_hash = _dimension_hash(client_address or "unknown")
        pair_hash = _dimension_hash(f"{client_address or 'unknown'}\0{email_dimension}")
        return (
            f"{self._prefix}pair:{pair_hash}",
            f"{self._prefix}address:{address_hash}",
        )


def _dimension_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
