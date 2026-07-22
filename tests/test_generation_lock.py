import pytest

from backend.app.generation_lock import AddressGenerationInProgress, AddressGenerationRegistry


@pytest.mark.asyncio
async def test_same_normalized_address_cannot_generate_twice_concurrently() -> None:
    registry = AddressGenerationRegistry()

    async with registry.hold("100, rue Sainte-Catherine, Montréal"):
        with pytest.raises(AddressGenerationInProgress):
            async with registry.hold("100 rue sainte catherine montreal"):
                pass

    async with registry.hold("100 rue Sainte-Catherine Montréal"):
        pass


@pytest.mark.asyncio
async def test_different_addresses_can_generate_concurrently() -> None:
    registry = AddressGenerationRegistry()

    async with registry.hold("100 rue Principale, Québec"):
        async with registry.hold("200 rue Principale, Québec"):
            pass
