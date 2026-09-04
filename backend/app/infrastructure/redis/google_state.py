from __future__ import annotations

import hashlib
import json
import logging
import math
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from time import perf_counter
from typing import Any, cast

from redis.asyncio import Redis
from redis.exceptions import NoScriptError, RedisError

from ...application.errors import (
    GoogleProtectionUnavailable,
    GoogleSearchInProgress,
    InvalidGoogleSelectionGrant,
    InvalidMapSnapshotGrant,
    MapSnapshotGrantInProgress,
)
from ...application.models import GoogleAccessOwner, MapPoint, MapSnapshot
from ...application.ports.metrics import MetricsRecorder, NullMetricsRecorder
from ...application.ports.prospect import GoogleSelectionGrantStore

logger = logging.getLogger(__name__)
type RedisScriptArgument = bytes | str | int | float

RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

CLAIM_MAP_GRANT_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw then return {0} end
local ok, grant = pcall(cjson.decode, raw)
if not ok or type(grant) ~= 'table' then return {3} end
if grant.schema_version ~= 1 or grant.user_id ~= ARGV[1] or grant.organization_id ~= ARGV[2] then return {0} end
if grant.state == 'claimed' then return {1} end
if grant.state ~= 'available' then return {3} end
grant.state = 'claimed'
grant.claim_id = ARGV[3]
redis.call('SET', KEYS[1], cjson.encode(grant), 'KEEPTTL')
return {2, raw}
"""

FINALIZE_MAP_GRANT_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw then return 0 end
local ok, grant = pcall(cjson.decode, raw)
if not ok or type(grant) ~= 'table' then return 0 end
if grant.schema_version == 1 and grant.user_id == ARGV[1] and grant.organization_id == ARGV[2]
   and grant.state == 'claimed' and grant.claim_id == ARGV[3] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

RESOLVE_SELECTION_GRANT_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw then return {0} end
local ok, grant = pcall(cjson.decode, raw)
if not ok or type(grant) ~= 'table' then return {2} end
if grant.schema_version ~= 1 or grant.user_id ~= ARGV[1] or grant.organization_id ~= ARGV[2] then return {0} end
return {1, raw}
"""


class RedisGenerationGuard:
    """Verrou de recherche partagé entre toutes les instances API."""

    def __init__(
        self,
        client: Redis,
        *,
        environment: str,
        ttl_seconds: float,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._client = client
        self._scripts = _RedisScriptExecutor(client)
        self._ttl_milliseconds = _milliseconds(ttl_seconds)
        self._prefix = f"prospect:{{{environment}}}:v1:google:"
        self._metrics = metrics or NullMetricsRecorder()

    @asynccontextmanager
    async def hold(self, owner: GoogleAccessOwner) -> AsyncIterator[None]:
        key = self._key(owner)
        lock_owner = secrets.token_urlsafe(32)
        started_at = perf_counter()
        try:
            acquired = await self._client.set(key, lock_owner, nx=True, px=self._ttl_milliseconds)
        except RedisError as error:
            self._metrics.record_redis_operation("lock_acquire", "unavailable", perf_counter() - started_at)
            raise GoogleProtectionUnavailable from error
        if not acquired:
            self._metrics.record_redis_operation("lock_acquire", "contended", perf_counter() - started_at)
            raise GoogleSearchInProgress
        self._metrics.record_redis_operation("lock_acquire", "accepted", perf_counter() - started_at)
        try:
            yield
        finally:
            try:
                release_started_at = perf_counter()
                await self._scripts.execute("release-lock", RELEASE_LOCK_SCRIPT, 1, key, lock_owner)
                self._metrics.record_redis_operation("lock_release", "accepted", perf_counter() - release_started_at)
            except RedisError:
                self._metrics.record_redis_operation("lock_release", "failed", perf_counter() - release_started_at)
                # Le TTL protège d'un processus arrêté. Un succès métier ne doit jamais être masqué ici.
                logger.warning("Impossible de libérer un verrou de recherche Google partagé.")

    def _key(self, owner: GoogleAccessOwner) -> str:
        return f"{self._prefix}{{{owner.organization_id}}}:search-lock:{owner.user_id}"


class RedisMapSnapshotGrantStore:
    """Concessions Static Maps éphémères, liées au propriétaire et terminales."""

    def __init__(
        self,
        client: Redis,
        *,
        environment: str,
        ttl_seconds: float,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._client = client
        self._scripts = _RedisScriptExecutor(client)
        self._ttl_seconds = _seconds(ttl_seconds)
        self._prefix = f"prospect:{{{environment}}}:v1:map-grant:"
        self._metrics = metrics or NullMetricsRecorder()

    async def issue(self, payload: MapSnapshot, owner: GoogleAccessOwner) -> str:
        serialized = _serialize_map_grant(payload, owner)
        for _ in range(3):
            token = secrets.token_urlsafe(32)
            started_at = perf_counter()
            try:
                created = await self._client.set(self._key(token), serialized, nx=True, ex=self._ttl_seconds)
            except RedisError as error:
                self._metrics.record_redis_operation("map_claim", "unavailable", perf_counter() - started_at)
                raise GoogleProtectionUnavailable from error
            if created:
                self._metrics.record_redis_operation("map_claim", "accepted", perf_counter() - started_at)
                self._metrics.record_map_grant("issued", "accepted")
                return token
        self._metrics.record_map_grant("issued", "failed")
        raise GoogleProtectionUnavailable("Impossible d’émettre une concession de carte unique.")

    @asynccontextmanager
    async def redeem(self, token: str, owner: GoogleAccessOwner) -> AsyncIterator[MapSnapshot]:
        key = self._key(token)
        claim_id = secrets.token_urlsafe(32)
        started_at = perf_counter()
        try:
            result = cast(
                list[Any],
                await self._scripts.execute(
                    "claim-map-grant",
                    CLAIM_MAP_GRANT_SCRIPT,
                    1,
                    key,
                    str(owner.user_id),
                    str(owner.organization_id),
                    claim_id,
                ),
            )
        except RedisError as error:
            self._metrics.record_redis_operation("map_claim", "unavailable", perf_counter() - started_at)
            raise GoogleProtectionUnavailable from error
        status = _script_status(result)
        if status == 0:
            self._metrics.record_map_grant("rejected", "rejected")
            raise InvalidMapSnapshotGrant
        if status == 1:
            self._metrics.record_map_grant("claimed", "contended")
            raise MapSnapshotGrantInProgress
        if status != 2 or len(result) != 2:
            self._metrics.record_map_grant("rejected", "failed")
            raise GoogleProtectionUnavailable("La concession de carte Redis est invalide.")
        self._metrics.record_redis_operation("map_claim", "accepted", perf_counter() - started_at)
        self._metrics.record_map_grant("claimed", "accepted")
        try:
            snapshot = _deserialize_map_grant(_as_text(result[1]), owner)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            await self._discard_corrupt(key, owner, claim_id)
            raise GoogleProtectionUnavailable("La concession de carte Redis est invalide.") from None
        try:
            yield snapshot
        finally:
            try:
                finalized_at = perf_counter()
                await self._scripts.execute(
                    "finalize-map-grant",
                    FINALIZE_MAP_GRANT_SCRIPT,
                    1,
                    key,
                    str(owner.user_id),
                    str(owner.organization_id),
                    claim_id,
                )
                self._metrics.record_redis_operation("map_finalize", "accepted", perf_counter() - finalized_at)
            except RedisError:
                self._metrics.record_redis_operation("map_finalize", "failed", perf_counter() - finalized_at)
                # La concession reste claimed jusqu'à TTL : aucun second appel Maps n'est autorisé.
                logger.warning("Impossible de finaliser une concession de carte Google partagée.")

    async def _discard_corrupt(self, key: str, owner: GoogleAccessOwner, claim_id: str) -> None:
        try:
            await self._scripts.execute(
                "finalize-map-grant",
                FINALIZE_MAP_GRANT_SCRIPT,
                1,
                key,
                str(owner.user_id),
                str(owner.organization_id),
                claim_id,
            )
        except RedisError:
            logger.warning("Impossible de supprimer une concession de carte corrompue.")

    def _key(self, token: str) -> str:
        return f"{self._prefix}{_token_hash(token)}"


class RedisGoogleSelectionGrantStore(GoogleSelectionGrantStore):
    """Sélection Google partagée, non destructive et strictement propriétaire."""

    def __init__(
        self,
        client: Redis,
        *,
        environment: str,
        ttl_seconds: int,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._client = client
        self._scripts = _RedisScriptExecutor(client)
        self._ttl_seconds = _seconds(ttl_seconds)
        self._prefix = f"prospect:{{{environment}}}:v1:selection-grant:"
        self._metrics = metrics or NullMetricsRecorder()

    async def issue(self, place_ids: tuple[str, ...], owner: GoogleAccessOwner, *, now: datetime) -> str:
        del now  # Redis est l'autorité de TTL ; le paramètre de port est conservé pour compatibilité.
        unique_place_ids = tuple(dict.fromkeys(place_id for place_id in place_ids if place_id))
        if len(unique_place_ids) > 20 or any(len(place_id) > 512 for place_id in unique_place_ids):
            raise ValueError("Une sélection Google ne peut pas contenir plus de vingt établissements.")
        serialized = json.dumps(
            {
                "schema_version": 1,
                "user_id": str(owner.user_id),
                "organization_id": str(owner.organization_id),
                "place_ids": list(unique_place_ids),
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )
        for _ in range(3):
            token = secrets.token_urlsafe(32)
            started_at = perf_counter()
            try:
                created = await self._client.set(self._key(token), serialized, nx=True, ex=self._ttl_seconds)
            except RedisError as error:
                self._metrics.record_redis_operation("selection_issue", "unavailable", perf_counter() - started_at)
                raise GoogleProtectionUnavailable from error
            if created:
                self._metrics.record_redis_operation("selection_issue", "accepted", perf_counter() - started_at)
                self._metrics.record_selection_grant("issued", "accepted")
                return token
        self._metrics.record_selection_grant("issued", "failed")
        raise GoogleProtectionUnavailable("Impossible d’émettre une sélection Google unique.")

    async def resolve(self, token: str, owner: GoogleAccessOwner, *, now: datetime) -> tuple[str, ...]:
        del now
        started_at = perf_counter()
        try:
            result = cast(
                list[Any],
                await self._scripts.execute(
                    "resolve-selection-grant",
                    RESOLVE_SELECTION_GRANT_SCRIPT,
                    1,
                    self._key(token),
                    str(owner.user_id),
                    str(owner.organization_id),
                ),
            )
        except RedisError as error:
            self._metrics.record_redis_operation("selection_resolve", "unavailable", perf_counter() - started_at)
            raise GoogleProtectionUnavailable from error
        status = _script_status(result)
        if status == 0:
            self._metrics.record_selection_grant("rejected", "rejected")
            raise InvalidGoogleSelectionGrant
        if status != 1 or len(result) != 2:
            self._metrics.record_selection_grant("rejected", "failed")
            raise GoogleProtectionUnavailable("La sélection Google Redis est invalide.")
        try:
            resolved = _deserialize_selection_grant(_as_text(result[1]), owner)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise GoogleProtectionUnavailable("La sélection Google Redis est invalide.") from None
        self._metrics.record_redis_operation("selection_resolve", "accepted", perf_counter() - started_at)
        self._metrics.record_selection_grant("resolved", "accepted")
        return resolved

    def _key(self, token: str) -> str:
        return f"{self._prefix}{_token_hash(token)}"


class _RedisScriptExecutor:
    """Cache de script par adaptateur, avec un seul rejeu sûr après NOSCRIPT."""

    def __init__(self, client: Redis) -> None:
        self._client = client
        self._sha_by_name: dict[str, str] = {}

    async def execute(self, name: str, source: str, key_count: int, *arguments: RedisScriptArgument) -> object:
        sha = self._sha_by_name.get(name)
        if sha is None:
            sha = await self._load(name, source)
        try:
            return await self._client.evalsha(sha, key_count, *arguments)
        except NoScriptError:
            # NOSCRIPT garantit que l'effet n'a pas eu lieu : un seul rechargement est donc sûr.
            sha = await self._load(name, source)
            return await self._client.evalsha(sha, key_count, *arguments)

    async def _load(self, name: str, source: str) -> str:
        loaded = await self._client.script_load(source)
        sha = _as_text(loaded)
        self._sha_by_name[name] = sha
        return sha


def _serialize_map_grant(payload: MapSnapshot, owner: GoogleAccessOwner) -> str:
    _validate_snapshot(payload)
    return json.dumps(
        {
            "schema_version": 1,
            "user_id": str(owner.user_id),
            "organization_id": str(owner.organization_id),
            "state": "available",
            "claim_id": None,
            "center_latitude": payload.center_latitude,
            "center_longitude": payload.center_longitude,
            "radius_km": payload.radius_km,
            "points": [{"latitude": point.latitude, "longitude": point.longitude} for point in payload.points],
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _deserialize_map_grant(raw: str, owner: GoogleAccessOwner) -> MapSnapshot:
    grant = _load_object(raw)
    if (
        grant["schema_version"] != 1
        or grant["user_id"] != str(owner.user_id)
        or grant["organization_id"] != str(owner.organization_id)
        or grant["state"] != "available"
        or grant["claim_id"] is not None
    ):
        raise ValueError("Concession de carte invalide.")
    points_raw = grant["points"]
    if not isinstance(points_raw, list) or len(points_raw) > 20:
        raise ValueError("Points de carte invalides.")
    snapshot = MapSnapshot(
        center_latitude=_finite_float(grant["center_latitude"], latitude=True),
        center_longitude=_finite_float(grant["center_longitude"], longitude=True),
        radius_km=_finite_float(grant["radius_km"], positive=True),
        points=[
            MapPoint(
                latitude=_finite_float(_mapping(point)["latitude"], latitude=True),
                longitude=_finite_float(_mapping(point)["longitude"], longitude=True),
            )
            for point in points_raw
        ],
    )
    _validate_snapshot(snapshot)
    return snapshot


def _deserialize_selection_grant(raw: str, owner: GoogleAccessOwner) -> tuple[str, ...]:
    grant = _load_object(raw)
    if (
        grant["schema_version"] != 1
        or grant["user_id"] != str(owner.user_id)
        or grant["organization_id"] != str(owner.organization_id)
    ):
        raise ValueError("Sélection Google invalide.")
    place_ids = grant["place_ids"]
    if (
        not isinstance(place_ids, list)
        or len(place_ids) > 20
        or any(not isinstance(value, str) or not value or len(value) > 512 for value in place_ids)
    ):
        raise ValueError("Établissements sélectionnés invalides.")
    if len(set(place_ids)) != len(place_ids):
        raise ValueError("Établissements sélectionnés dupliqués.")
    return tuple(place_ids)


def _validate_snapshot(snapshot: MapSnapshot) -> None:
    _finite_float(snapshot.center_latitude, latitude=True)
    _finite_float(snapshot.center_longitude, longitude=True)
    _finite_float(snapshot.radius_km, positive=True)
    if len(snapshot.points) > 20:
        raise ValueError("Une carte ne peut pas contenir plus de vingt points.")
    for point in snapshot.points:
        _finite_float(point.latitude, latitude=True)
        _finite_float(point.longitude, longitude=True)


def _finite_float(value: object, *, latitude: bool = False, longitude: bool = False, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("Valeur numérique invalide.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Valeur non finie.")
    if latitude and not -90 <= result <= 90:
        raise ValueError("Latitude invalide.")
    if longitude and not -180 <= result <= 180:
        raise ValueError("Longitude invalide.")
    if positive and result <= 0:
        raise ValueError("Valeur positive attendue.")
    return result


def _load_object(raw: str) -> dict[str, Any]:
    return _mapping(json.loads(raw))


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Objet JSON attendu.")
    return cast(dict[str, Any], value)


def _script_status(result: list[Any]) -> int:
    if not result or isinstance(result[0], bool):
        return -1
    try:
        return int(result[0])
    except (TypeError, ValueError):
        return -1


def _as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise ValueError("Texte Redis attendu.")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _seconds(value: float | int) -> int:
    if value <= 0:
        raise ValueError("Le TTL Redis doit être positif.")
    return max(1, math.ceil(value))


def _milliseconds(value: float) -> int:
    if value <= 0:
        raise ValueError("Le TTL Redis doit être positif.")
    return max(1, math.ceil(value * 1_000))
