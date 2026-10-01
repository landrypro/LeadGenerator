import pytest

from backend.app.application.models import GooglePlaceSearchCriteria
from backend.app.infrastructure.google.simulated import SimulatedGooglePlacesGateway


@pytest.mark.asyncio
async def test_google_simulator_returns_only_deterministic_synthetic_results() -> None:
    gateway = SimulatedGooglePlacesGateway()

    results = await gateway.search(
        GooglePlaceSearchCriteria(query="texte qui ne doit pas être conservé", center_latitude=0, center_longitude=0)
    )

    assert [result.place_id for result in results] == [
        "e2e06-simulated-place-01",
        "e2e06-simulated-place-02",
    ]
    assert all(result.latitude is None and result.longitude is None for result in results)
    assert all(result.service_area_business for result in results)
