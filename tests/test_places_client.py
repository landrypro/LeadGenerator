import httpx
import pytest

from backend.app.geo import SearchTile
from backend.app.models import SearchRequest
from backend.app.places import GooglePlacesClient, GooglePlacesSettings


@pytest.mark.asyncio
async def test_retries_after_429_without_real_google_call():
    attempts = 0

    async def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": {"message": "quota"}})
        return httpx.Response(200, json={"places": [], "nextPageToken": "next"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GooglePlacesClient(
            GooglePlacesSettings(api_key="fake-key", max_retries=1, retry_base_seconds=0),
            http_client,
        )
        page = await client.search_page(SearchRequest(query="plombier"), SearchTile(1, 46.8, -71.2, 1000))

    assert attempts == 2
    assert page.next_page_token == "next"


@pytest.mark.asyncio
async def test_contact_field_mask_is_optional():
    masks = []

    async def handler(request):
        masks.append(request.headers["X-Goog-FieldMask"])
        return httpx.Response(200, json={"places": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GooglePlacesClient(GooglePlacesSettings(api_key="fake"), http_client)
        tile = SearchTile(1, 46.8, -71.2, 1000)
        await client.search_page(SearchRequest(query="plombier", contact_fields=False), tile)
        await client.search_page(SearchRequest(query="plombier", contact_fields=True), tile)

    assert "nationalPhoneNumber" not in masks[0]
    assert "nationalPhoneNumber" in masks[1]
    assert "websiteUri" in masks[1]
