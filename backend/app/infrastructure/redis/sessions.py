from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from ...application.errors import AuthenticationServiceUnavailable
from ...domain.identity import CreatedSession, SessionRecord

CREATE_SESSION_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
redis.call('SADD', KEYS[2], ARGV[3])
local current_ttl = redis.call('TTL', KEYS[2])
if current_ttl < tonumber(ARGV[4]) then
  redis.call('EXPIRE', KEYS[2], ARGV[4])
end
return 1
"""

LOAD_AND_TOUCH_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw then return nil end
local decoded_ok, decoded = pcall(cjson.decode, raw)
if not decoded_ok or type(decoded) ~= 'table' or not decoded.user_id or
   not decoded.absolute_expires_at or not decoded.last_seen_at then
  redis.call('DEL', KEYS[1])
  return nil
end
local now = tonumber(ARGV[1])
local idle = tonumber(ARGV[2])
if now >= tonumber(decoded.absolute_expires_at) or now - tonumber(decoded.last_seen_at) >= idle then
  redis.call('DEL', KEYS[1])
  redis.call('SREM', ARGV[3] .. decoded.user_id, ARGV[4])
  return nil
end
decoded.last_seen_at = now
local ttl = math.floor(math.min(idle, tonumber(decoded.absolute_expires_at) - now))
if ttl < 1 then
  redis.call('DEL', KEYS[1])
  redis.call('SREM', ARGV[3] .. decoded.user_id, ARGV[4])
  return nil
end
local updated = cjson.encode(decoded)
redis.call('SET', KEYS[1], updated, 'EX', ttl)
return updated
"""

REVOKE_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if raw then
  local decoded_ok, decoded = pcall(cjson.decode, raw)
  if decoded_ok and type(decoded) == 'table' and decoded.user_id then
    redis.call('SREM', ARGV[1] .. decoded.user_id, ARGV[2])
  end
end
return redis.call('DEL', KEYS[1])
"""

REVOKE_USER_SCRIPT = """
local hashes = redis.call('SMEMBERS', KEYS[1])
for _, token_hash in ipairs(hashes) do
  redis.call('DEL', ARGV[1] .. token_hash)
end
redis.call('DEL', KEYS[1])
return #hashes
"""

REVOKE_USER_BEFORE_VERSION_SCRIPT = """
local hashes = redis.call('SMEMBERS', KEYS[1])
local removed = 0
local minimum_version = tonumber(ARGV[2])
for _, token_hash in ipairs(hashes) do
  local session_key = ARGV[1] .. token_hash
  local raw = redis.call('GET', session_key)
  if not raw then
    redis.call('SREM', KEYS[1], token_hash)
  else
    local decoded_ok, decoded = pcall(cjson.decode, raw)
    local version = decoded_ok and type(decoded) == 'table' and tonumber(decoded.user_version) or nil
    if not version or version < minimum_version then
      redis.call('DEL', session_key)
      redis.call('SREM', KEYS[1], token_hash)
      removed = removed + 1
    end
  end
end
if redis.call('SCARD', KEYS[1]) == 0 then redis.call('DEL', KEYS[1]) end
return removed
"""

ROTATE_SESSION_SCRIPT = """
if redis.call('EXISTS', KEYS[2]) == 1 then return 0 end
local old = redis.call('GET', KEYS[1])
if not old then return -1 end
local decoded_ok, decoded = pcall(cjson.decode, old)
if not decoded_ok or type(decoded) ~= 'table' or decoded.user_id ~= ARGV[3]
   or not decoded.absolute_expires_at then return -2 end
local replacement_ok, replacement = pcall(cjson.decode, ARGV[1])
if not replacement_ok or type(replacement) ~= 'table' then return -2 end
local remaining = math.floor(tonumber(decoded.absolute_expires_at) - tonumber(ARGV[7]))
if remaining < 1 then return -3 end
replacement.absolute_expires_at = decoded.absolute_expires_at
local replacement_raw = cjson.encode(replacement)
local ttl = math.floor(math.min(tonumber(ARGV[2]), remaining))
redis.call('SET', KEYS[2], replacement_raw, 'EX', ttl)
redis.call('SREM', KEYS[3], ARGV[5])
redis.call('SADD', KEYS[3], ARGV[4])
local current_ttl = redis.call('TTL', KEYS[3])
if current_ttl < tonumber(ARGV[6]) then redis.call('EXPIRE', KEYS[3], ARGV[6]) end
redis.call('DEL', KEYS[1])
return replacement_raw
"""


class RedisSessionStore:
    def __init__(
        self,
        client: Redis,
        *,
        environment: str,
        idle_seconds: int,
        absolute_seconds: int,
    ) -> None:
        self._client = client
        self._idle_seconds = idle_seconds
        self._absolute_seconds = absolute_seconds
        self._session_prefix = f"prospect:{environment}:session:"
        self._user_index_prefix = f"prospect:{environment}:user-sessions:"

    async def create(
        self,
        *,
        user_id: UUID,
        active_organization_id: UUID | None,
        user_version: int,
        now: datetime,
    ) -> CreatedSession:
        issued_at = _as_utc(now)
        record = SessionRecord(
            user_id=user_id,
            active_organization_id=active_organization_id,
            issued_at=issued_at,
            last_seen_at=issued_at,
            absolute_expires_at=issued_at + timedelta(seconds=self._absolute_seconds),
            csrf_token=secrets.token_urlsafe(32),
            user_version=user_version,
        )
        payload = _serialize(record)
        try:
            for _ in range(3):
                token = secrets.token_urlsafe(32)
                token_hash = _token_hash(token)
                key = self._session_key(token_hash)
                index_key = self._user_index_key(user_id)
                created = await self._client.eval(
                    CREATE_SESSION_SCRIPT,
                    2,
                    key,
                    index_key,
                    payload,
                    self._idle_seconds,
                    token_hash,
                    self._absolute_seconds,
                )
                if created:
                    return CreatedSession(token=token, record=record)
        except RedisError as error:
            raise AuthenticationServiceUnavailable from error
        raise AuthenticationServiceUnavailable("Impossible de créer un identifiant de session unique.")

    async def load_and_touch(self, token: str, now: datetime) -> SessionRecord | None:
        token_hash = _token_hash(token)
        try:
            raw = await self._client.eval(
                LOAD_AND_TOUCH_SCRIPT,
                1,
                self._session_key(token_hash),
                int(_as_utc(now).timestamp()),
                self._idle_seconds,
                self._user_index_prefix,
                token_hash,
            )
        except RedisError as error:
            raise AuthenticationServiceUnavailable from error
        if raw is None:
            return None
        try:
            return _deserialize(cast(bytes | str, raw))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            await self.revoke(token)
            return None

    async def rotate(
        self,
        *,
        current_token: str,
        user_id: UUID,
        active_organization_id: UUID | None,
        user_version: int,
        now: datetime,
    ) -> CreatedSession:
        issued_at = _as_utc(now)
        record = SessionRecord(
            user_id=user_id,
            active_organization_id=active_organization_id,
            issued_at=issued_at,
            last_seen_at=issued_at,
            absolute_expires_at=issued_at + timedelta(seconds=self._absolute_seconds),
            csrf_token=secrets.token_urlsafe(32),
            user_version=user_version,
        )
        payload = _serialize(record)
        current_hash = _token_hash(current_token)
        try:
            for _ in range(3):
                token = secrets.token_urlsafe(32)
                token_hash = _token_hash(token)
                rotated = await self._client.eval(
                    ROTATE_SESSION_SCRIPT,
                    3,
                    self._session_key(current_hash),
                    self._session_key(token_hash),
                    self._user_index_key(user_id),
                    payload,
                    self._idle_seconds,
                    str(user_id),
                    token_hash,
                    current_hash,
                    self._absolute_seconds,
                    int(issued_at.timestamp()),
                )
                if isinstance(rotated, (bytes, str)):
                    return CreatedSession(token=token, record=_deserialize(rotated))
                if rotated in {-1, -2, -3}:
                    raise AuthenticationServiceUnavailable("La session courante ne peut pas être renouvelée.")
        except RedisError as error:
            raise AuthenticationServiceUnavailable from error
        raise AuthenticationServiceUnavailable("Impossible de faire tourner l’identifiant de session.")

    async def revoke(self, token: str) -> None:
        token_hash = _token_hash(token)
        try:
            await self._client.eval(
                REVOKE_SCRIPT,
                1,
                self._session_key(token_hash),
                self._user_index_prefix,
                token_hash,
            )
        except RedisError as error:
            raise AuthenticationServiceUnavailable from error

    async def revoke_user(self, user_id: UUID) -> None:
        try:
            await self._client.eval(
                REVOKE_USER_SCRIPT,
                1,
                self._user_index_key(user_id),
                self._session_prefix,
            )
        except RedisError as error:
            raise AuthenticationServiceUnavailable from error

    async def revoke_user_before_version(self, user_id: UUID, minimum_valid_version: int) -> None:
        if minimum_valid_version < 1:
            raise ValueError("La version minimale de session doit être positive.")
        try:
            await self._client.eval(
                REVOKE_USER_BEFORE_VERSION_SCRIPT,
                1,
                self._user_index_key(user_id),
                self._session_prefix,
                minimum_valid_version,
            )
        except RedisError as error:
            raise AuthenticationServiceUnavailable from error

    def _session_key(self, token_hash: str) -> str:
        return f"{self._session_prefix}{token_hash}"

    def _user_index_key(self, user_id: UUID) -> str:
        return f"{self._user_index_prefix}{user_id}"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _serialize(record: SessionRecord) -> str:
    payload: dict[str, Any] = {
        "user_id": str(record.user_id),
        "active_organization_id": str(record.active_organization_id) if record.active_organization_id else None,
        "issued_at": int(record.issued_at.timestamp()),
        "last_seen_at": int(record.last_seen_at.timestamp()),
        "absolute_expires_at": int(record.absolute_expires_at.timestamp()),
        "csrf_token": record.csrf_token,
        "user_version": record.user_version,
    }
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def _deserialize(raw: bytes | str) -> SessionRecord:
    payload = json.loads(raw)
    active_organization_id = payload["active_organization_id"]
    return SessionRecord(
        user_id=UUID(payload["user_id"]),
        active_organization_id=UUID(active_organization_id) if active_organization_id else None,
        issued_at=datetime.fromtimestamp(int(payload["issued_at"]), UTC),
        last_seen_at=datetime.fromtimestamp(int(payload["last_seen_at"]), UTC),
        absolute_expires_at=datetime.fromtimestamp(int(payload["absolute_expires_at"]), UTC),
        csrf_token=str(payload["csrf_token"]),
        user_version=int(payload["user_version"]),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Une date de session doit inclure un fuseau horaire.")
    return value.astimezone(UTC)
