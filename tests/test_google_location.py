from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from backend.app.application.models import GoogleAccessContext
from backend.app.infrastructure.google.location import GoogleLocationResolver, InvalidLocationSelection
from backend.app.infrastructure.google.places import GooglePlacesError, GooglePlacesSettings


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.used: set[str] = set()

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, _key: str, _seconds: int) -> None:
        return None

    async def set(self, key: str, _value: str, *, ex: int, nx: bool) -> bool:
        assert ex == 300 and nx
        if key in self.used:
            return False
        self.used.add(key)
        return True


@pytest.mark.asyncio
async def test_location_suggestion_and_resolution_use_one_tenant_bound_selection() -> None:
    calls: list[httpx.Request] = []

    def google(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith(":autocomplete"):
            return httpx.Response(
                200,
                json={
                    "suggestions": [
                        {
                            "placePrediction": {
                                "placeId": "ChIJ-test",
                                "text": {"text": "Montréal, Québec, Canada"},
                            }
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "location": {"latitude": 45.5017, "longitude": -73.5673},
                "addressComponents": [{"types": ["country"], "shortText": "CA"}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(google)) as client:
        resolver = GoogleLocationResolver(GooglePlacesSettings("secret-key"), b"a" * 32, FakeRedis(), client)
        access = GoogleAccessContext(uuid4(), uuid4(), uuid4())
        suggestions = await resolver.suggest(
            text="Montr",
            area="Québec, Canada",
            scope="locality",
            language="fr",
            session_token=uuid4(),
            access=access,
            country_code="CA",
        )
        assert len(suggestions) == 1
        assert b"Montr, Qu\xc3\xa9bec, Canada" in calls[0].content
        assert b'"includedRegionCodes":["CA"]' in calls[0].content
        assert b"sessionToken" in calls[0].content
        with pytest.raises(InvalidLocationSelection):
            await resolver.resolve(
                selection_token=suggestions[0]["selection_token"],
                access=GoogleAccessContext(uuid4(), access.organization_id, access.membership_id),
            )
        resolved = await resolver.resolve(selection_token=suggestions[0]["selection_token"], access=access)
        with pytest.raises(InvalidLocationSelection):
            await resolver.resolve(selection_token=suggestions[0]["selection_token"], access=access)

    assert resolved == {
        "label": "Montréal, Québec, Canada",
        "scope": "locality",
        "latitude": 45.5017,
        "longitude": -73.5673,
        "region_code": "CA",
    }
    assert len(calls) == 2
    assert calls[1].url.params["sessionToken"]
    assert calls[1].headers["X-Goog-FieldMask"] == "location,addressComponents"


@pytest.mark.asyncio
async def test_location_rejects_tampered_selection_without_google_call() -> None:
    calls: list[httpx.Request] = []

    def google(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "suggestions": [
                    {
                        "placePrediction": {
                            "placeId": "ChIJ-test",
                            "text": {"text": "Canada"},
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(google)) as client:
        resolver = GoogleLocationResolver(GooglePlacesSettings("secret-key"), b"a" * 32, FakeRedis(), client)
        access = GoogleAccessContext(uuid4(), uuid4(), uuid4())
        items = await resolver.suggest(
            text="Cana", area="", scope="area", language="en", session_token=uuid4(), access=access
        )
        token = items[0]["selection_token"]
        with pytest.raises(InvalidLocationSelection):
            await resolver.resolve(selection_token=("A" if token[0] != "A" else "B") + token[1:], access=access)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_location_requests_stop_before_provider_when_rate_limit_is_reached() -> None:
    requests: list[httpx.Request] = []

    def google(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"suggestions": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(google)) as client:
        resolver = GoogleLocationResolver(GooglePlacesSettings("secret-key"), b"a" * 32, FakeRedis(), client)
        access = GoogleAccessContext(uuid4(), uuid4(), uuid4())
        for _ in range(30):
            await resolver.suggest(
                text="Cana", area="", scope="area", language="fr", session_token=uuid4(), access=access
            )
        with pytest.raises(GooglePlacesError) as captured:
            await resolver.suggest(
                text="Cana", area="", scope="area", language="fr", session_token=uuid4(), access=access
            )

    assert captured.value.status_code == 429
    assert len(requests) == 30
