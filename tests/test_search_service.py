from collections import deque

import pytest

from backend.app.models import SearchRequest
from backend.app.places import PlacesPage
from backend.app.search_service import LeadSearchService


class FakePlacesClient:
    def __init__(self, pages):
        self.pages = deque(pages)
        self.calls = []

    async def search_page(self, request, tile, page_token=None):
        self.calls.append((tile.index, page_token))
        return self.pages.popleft() if self.pages else PlacesPage([], None)


def place(place_id="place-1", lat=46.8139, lon=-71.2080, **overrides):
    value = {
        "id": place_id,
        "displayName": {"text": "Plomberie Boréale"},
        "formattedAddress": "100 rue Saint-Joseph, Québec",
        "location": {"latitude": lat, "longitude": lon},
        "googleMapsUri": "https://maps.google.com/?cid=1",
        "primaryType": "plumber",
        "businessStatus": "OPERATIONAL",
    }
    value.update(overrides)
    return value


@pytest.mark.asyncio
async def test_deduplicates_by_place_id_across_tiles():
    client = FakePlacesClient([PlacesPage([place()], None), PlacesPage([place()], None)])
    request = SearchRequest(query="plombier", max_tiles=2, max_pages=1, target=10)

    result = await LeadSearchService(client).search(request)

    assert len(result.leads) == 1
    assert result.stats.duplicates_removed == 1
    assert result.stats.zones_searched == 2


@pytest.mark.asyncio
async def test_filters_results_outside_global_radius():
    far_away = place(lat=45.5019, lon=-73.5674)
    client = FakePlacesClient([PlacesPage([far_away], None)])
    request = SearchRequest(query="plombier", radius_km=10, max_tiles=1)

    result = await LeadSearchService(client).search(request)

    assert result.leads == []
    assert result.stats.outside_radius_removed == 1


@pytest.mark.asyncio
async def test_keeps_service_area_business_without_location_as_unverified():
    service_area = place(location=None, pureServiceAreaBusiness=True, formattedAddress="")
    client = FakePlacesClient([PlacesPage([service_area], None)])
    request = SearchRequest(query="plombier", max_tiles=1, include_service_area_businesses=True)

    result = await LeadSearchService(client).search(request)

    assert len(result.leads) == 1
    assert result.leads[0].radius_verified is False
    assert result.stats.service_area_unverified == 1


@pytest.mark.asyncio
async def test_follows_next_page_token_and_stops_at_page_limit():
    client = FakePlacesClient(
        [
            PlacesPage([place("one")], "token-2"),
            PlacesPage([place("two")], "token-3"),
        ]
    )
    request = SearchRequest(query="plombier", max_tiles=1, max_pages=2, target=10)

    result = await LeadSearchService(client).search(request)

    assert len(result.leads) == 2
    assert client.calls == [(1, None), (1, "token-2")]
    assert result.stats.api_calls == 2
