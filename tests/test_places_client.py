import json

import httpx
import pytest

from backend.app.application.models import GooglePlaceSearchCriteria
from backend.app.places import (
    PAGE_SIZE,
    PLACE_LIST_FIELDS,
    GooglePlacesClient,
    GooglePlacesError,
    GooglePlacesSettings,
)


def google_place(index: int) -> dict[str, object]:
    return {
        "id": f"place-{index}",
        "displayName": {"text": f"Entreprise {index}"},
        "formattedAddress": "Québec",
        "location": {"latitude": 46.8139, "longitude": -71.2080},
        "nationalPhoneNumber": "418-555-0100",
        "internationalPhoneNumber": "+14185550100",
        "websiteUri": "https://example.test",
    }


@pytest.mark.asyncio
async def test_text_search_is_called_once_without_following_next_page_token() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "places": [google_place(index) for index in range(25)],
                "nextPageToken": "must-not-be-followed",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GooglePlacesClient(GooglePlacesSettings(api_key="fake-key"), http_client)
        places = await client.search(GooglePlaceSearchCriteria(query="plombier"))

    assert len(requests) == 1
    assert len(places) == PAGE_SIZE == 20
    payload = json.loads(requests[0].content)
    assert payload["pageSize"] == 20
    assert "pageToken" not in payload
    assert "nextPageToken" not in PLACE_LIST_FIELDS


@pytest.mark.asyncio
async def test_list_field_mask_excludes_phone_and_website() -> None:
    field_masks: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        field_masks.append(request.headers["X-Goog-FieldMask"])
        return httpx.Response(200, json={"places": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GooglePlacesClient(GooglePlacesSettings(api_key="fake-key"), http_client)
        await client.search(GooglePlaceSearchCriteria(query="plombier"))

    assert len(field_masks) == 1
    assert "PhoneNumber" not in field_masks[0]
    assert "websiteUri" not in field_masks[0]


@pytest.mark.asyncio
async def test_google_error_is_not_retried() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, json={"error": {"message": "quota"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GooglePlacesClient(GooglePlacesSettings(api_key="fake-key"), http_client)
        with pytest.raises(GooglePlacesError) as captured:
            await client.search(GooglePlaceSearchCriteria(query="plombier"))

    assert attempts == 1
    assert captured.value.status_code == 429
