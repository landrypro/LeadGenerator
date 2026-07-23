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

    async with registry.hold("100 rue Principale, Québec"), registry.hold("200 rue Principale, Québec"):
        pass


def test_non_latin_addresses_do_not_collapse_to_the_same_key() -> None:
    beijing = AddressGenerationRegistry.address_key("北京市朝阳区")
    tokyo = AddressGenerationRegistry.address_key("東京都渋谷区")

    assert beijing != tokyo


def test_unicode_normalization_keeps_equivalent_addresses_together() -> None:
    accented = AddressGenerationRegistry.address_key("100, rue Sainte-Catherine, Montréal")
    plain_ascii = AddressGenerationRegistry.address_key("100 rue sainte catherine montreal")
    full_width = AddressGenerationRegistry.address_key("１００ rue Sainte-Catherine Montréal")

    assert accented == plain_ascii == full_width


def test_symbol_only_addresses_do_not_use_the_empty_string_hash() -> None:
    first = AddressGenerationRegistry.address_key("🏢🏢🏢🏢🏢")
    second = AddressGenerationRegistry.address_key("🏠🏠🏠🏠🏠")

    assert first != second
