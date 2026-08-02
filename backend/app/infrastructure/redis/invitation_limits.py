from __future__ import annotations

import hashlib
import hmac
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from ...application.errors import ProvisioningServiceUnavailable
from ...application.ports.provisioning import InvitationLimitStatus

CONSUME_SCRIPT = """
local address_count = redis.call('INCR', KEYS[1])
if address_count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local token_count = redis.call('INCR', KEYS[2])
if token_count == 1 then redis.call('EXPIRE', KEYS[2], ARGV[1]) end
local blocked = address_count > tonumber(ARGV[2]) or token_count > tonumber(ARGV[3])
local retry = math.max(redis.call('TTL', KEYS[1]), redis.call('TTL', KEYS[2]), 1)
return {blocked and 1 or 0, retry}
"""


class RedisInvitationRateLimiter:
    def __init__(
        self,
        client: Redis,
        *,
        environment: str,
        window_seconds: int,
        address_limit: int,
        token_limit: int,
        hmac_key: bytes,
    ) -> None:
        self._client = client
        self._window_seconds = window_seconds
        self._address_limit = address_limit
        self._token_limit = token_limit
        self._hmac_key = hmac_key
        self._prefix = f"prospect:{environment}:invitation-limit:"

    async def consume(self, *, client_address: str, token_hash: str) -> InvitationLimitStatus:
        address_dimension = self._hmac(client_address or "unknown")
        token_dimension = self._hmac(token_hash)
        try:
            raw = await self._client.eval(
                CONSUME_SCRIPT,
                2,
                f"{self._prefix}address:{address_dimension}",
                f"{self._prefix}token:{token_dimension}",
                self._window_seconds,
                self._address_limit,
                self._token_limit,
            )
        except RedisError as error:
            raise ProvisioningServiceUnavailable from error
        result = cast(list[int], raw)
        return InvitationLimitStatus(blocked=bool(result[0]), retry_after_seconds=max(1, int(result[1])))

    def _hmac(self, value: str) -> str:
        return hmac.new(self._hmac_key, value.encode("utf-8"), hashlib.sha256).hexdigest()
