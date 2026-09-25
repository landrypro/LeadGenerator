from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import TypedDict, cast
from urllib.parse import quote
from uuid import UUID

import httpx
from redis.asyncio import Redis

from ...application.models import GoogleAccessContext
from .places import GooglePlacesError, GooglePlacesSettings

AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
DETAILS_URL = "https://places.googleapis.com/v1/places/"
SELECTION_TTL = timedelta(minutes=5)


class InvalidLocationSelection(ValueError):
    pass


class LocationTokenPayload(TypedDict):
    place_id: str
    label: str
    scope: str
    language: str
    session_token: str
    user_id: str
    organization_id: str
    expires: int


class GoogleLocationResolver:
    """Temporary, tenant-bound place predictions and selected coordinates."""

    def __init__(
        self,
        settings: GooglePlacesSettings,
        signing_key: bytes,
        redis_client: Redis | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._key = hmac.new(signing_key, b"google-location-selection-v1", hashlib.sha256).digest()
        self._redis = redis_client
        self._client = http_client

    async def _limit(self, access: GoogleAccessContext) -> None:
        if self._redis is None:
            raise GooglePlacesError("La protection du choix de lieu est indisponible.")
        identity = hmac.new(self._key, str(access.user_id).encode(), hashlib.sha256).hexdigest()
        now = datetime.now(UTC)
        minute = int(now.timestamp()) // 60
        day = now.strftime("%Y%m%d")
        try:
            counts = []
            for key, ttl in (
                (f"google-location:{identity}:minute:{minute}", 120),
                (f"google-location:{identity}:day:{day}", 86400),
            ):
                count = await self._redis.incr(key)
                if count == 1:
                    await self._redis.expire(key, ttl)
                counts.append(count)
        except Exception as exc:
            raise GooglePlacesError("La protection du choix de lieu est indisponible.") from exc
        if counts[0] > 30 or counts[1] > 200:
            raise GooglePlacesError("Trop de recherches de lieux.", 429)

    async def suggest(
        self,
        *,
        text: str,
        area: str,
        scope: str,
        language: str,
        session_token: UUID,
        access: GoogleAccessContext,
        country_code: str = "",
        before_upstream: Callable[[], Awaitable[None]] | None = None,
    ) -> list[dict[str, str]]:
        await self._limit(access)
        body = {
            "input": f"{text}, {area}" if area and scope == "locality" else text,
            "languageCode": language,
            "includedPrimaryTypes": (
                ["country", "administrative_area_level_1", "administrative_area_level_2"]
                if scope == "area"
                else ["locality", "neighborhood", "sublocality", "sublocality_level_1", "postal_town"]
            ),
            "sessionToken": str(session_token),
        }
        if scope == "locality" and country_code:
            body["includedRegionCodes"] = [country_code]
        headers = {
            "X-Goog-Api-Key": self.settings.api_key,
            "X-Goog-FieldMask": "suggestions.placePrediction.placeId,suggestions.placePrediction.text.text",
            "Content-Type": "application/json",
        }
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.timeout_seconds)
        try:
            try:
                if before_upstream is not None:
                    await before_upstream()
                response = await client.post(AUTOCOMPLETE_URL, json=body, headers=headers)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise GooglePlacesError("Google Places est temporairement injoignable.") from exc
        finally:
            if owns_client:
                await client.aclose()
        if response.is_error:
            raise GooglePlacesError("Google Places a refusé l’autocomplétion.", response.status_code)
        try:
            data = response.json()
        except ValueError as exc:
            raise GooglePlacesError("La réponse des lieux Google est invalide.") from exc
        if not isinstance(data, dict):
            raise GooglePlacesError("La réponse des lieux Google est invalide.")
        suggestions = data.get("suggestions", [])
        if not isinstance(suggestions, list):
            raise GooglePlacesError("La réponse des lieux Google est invalide.")
        items = []
        for suggestion in suggestions[:5]:
            if not isinstance(suggestion, dict):
                continue
            prediction = suggestion.get("placePrediction") or {}
            if not isinstance(prediction, dict):
                continue
            place_id = prediction.get("placeId")
            text_data = prediction.get("text") or {}
            label = text_data.get("text") if isinstance(text_data, dict) else None
            if isinstance(place_id, str) and isinstance(label, str) and place_id and label:
                items.append(
                    {
                        "label": label,
                        "selection_token": self._sign(place_id, label, scope, language, session_token, access),
                    }
                )
        return items

    async def resolve(
        self,
        *,
        selection_token: str,
        access: GoogleAccessContext,
        before_upstream: Callable[[], Awaitable[None]] | None = None,
    ) -> dict[str, str | float]:
        await self._limit(access)
        payload = self._verify(selection_token, access)
        if self._redis is None:
            raise GooglePlacesError("La protection du choix de lieu est indisponible.")
        replay_key = "google-location:used:" + hmac.new(self._key, selection_token.encode(), hashlib.sha256).hexdigest()
        try:
            first_use = await self._redis.set(replay_key, "1", ex=300, nx=True)
        except Exception as exc:
            raise GooglePlacesError("La protection du choix de lieu est indisponible.") from exc
        if not first_use:
            raise InvalidLocationSelection("Cette proposition de lieu a déjà été utilisée.")
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.timeout_seconds)
        try:
            try:
                if before_upstream is not None:
                    await before_upstream()
                response = await client.get(
                    DETAILS_URL + quote(payload["place_id"], safe=""),
                    params={"languageCode": payload["language"], "sessionToken": payload["session_token"]},
                    headers={
                        "X-Goog-Api-Key": self.settings.api_key,
                        "X-Goog-FieldMask": "location,addressComponents",
                    },
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise GooglePlacesError("Google Places est temporairement injoignable.") from exc
        finally:
            if owns_client:
                await client.aclose()
        if response.is_error:
            raise GooglePlacesError("Google Places a refusé le lieu sélectionné.", response.status_code)
        try:
            details = response.json()
        except ValueError as exc:
            raise GooglePlacesError("La réponse du lieu Google est invalide.") from exc
        if not isinstance(details, dict):
            raise GooglePlacesError("La réponse du lieu Google est invalide.")
        location = details.get("location") or {}
        if not isinstance(location, dict):
            raise GooglePlacesError("La réponse du lieu Google est invalide.")
        latitude, longitude = location.get("latitude"), location.get("longitude")
        if (
            not isinstance(latitude, int | float)
            or not isinstance(longitude, int | float)
            or not math.isfinite(latitude)
            or not math.isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise GooglePlacesError("Le lieu sélectionné n’a pas de centre valide.")
        components = details.get("addressComponents") or []
        if not isinstance(components, list):
            raise GooglePlacesError("La réponse du lieu Google est invalide.")
        country = next(
            (
                component.get("shortText", "")
                for component in components
                if isinstance(component, dict) and "country" in component.get("types", [])
            ),
            "",
        )
        if not isinstance(country, str) or len(country) != 2:
            raise GooglePlacesError("Le pays du lieu sélectionné n’a pas pu être identifié.")
        return {
            "label": payload["label"],
            "scope": payload["scope"],
            "latitude": latitude,
            "longitude": longitude,
            "region_code": country.upper(),
        }

    def _sign(
        self, place_id: str, label: str, scope: str, language: str, session_token: UUID, access: GoogleAccessContext
    ) -> str:
        payload = {
            "place_id": place_id,
            "label": label,
            "scope": scope,
            "language": language,
            "session_token": str(session_token),
            "user_id": str(access.user_id),
            "organization_id": str(access.organization_id),
            "expires": int((datetime.now(UTC) + SELECTION_TTL).timestamp()),
        }
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        signature = hmac.new(self._key, raw, hashlib.sha256).digest()
        return f"{_encode(raw)}.{_encode(signature)}"

    def _verify(self, token: str, access: GoogleAccessContext) -> LocationTokenPayload:
        try:
            if len(token) > 2048:
                raise ValueError("length")
            data, signature = token.split(".", 1)
            raw = _decode(data)
            if not hmac.compare_digest(_decode(signature), hmac.new(self._key, raw, hashlib.sha256).digest()):
                raise ValueError("signature")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("payload")
            for key in ("place_id", "label", "scope", "language", "session_token", "user_id", "organization_id"):
                if not isinstance(payload.get(key), str):
                    raise ValueError("payload")
            if not isinstance(payload.get("expires"), int):
                raise ValueError("payload")
            if (
                payload["user_id"] != str(access.user_id)
                or payload["organization_id"] != str(access.organization_id)
                or payload["expires"] < datetime.now(UTC).timestamp()
                or payload["scope"] not in {"area", "locality"}
            ):
                raise ValueError("scope")
            return cast(LocationTokenPayload, payload)
        except (ValueError, KeyError, TypeError, binascii.Error, UnicodeDecodeError) as exc:
            raise InvalidLocationSelection("La proposition de lieu a expiré ou n’est pas valide.") from exc


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
