from __future__ import annotations

from collections.abc import AsyncIterator
from os import utime
from time import time

import pytest

from backend.app.application.use_cases.csv_import import _parse_csv, _validate_mapping
from backend.app.infrastructure.imports.local_csv_store import LocalTemporaryCsvFileStore


def test_csv_preview_parses_utf8_bom_and_keeps_only_declared_cells() -> None:
    headers, rows = _parse_csv("\ufeffEntreprise,Courriel\r\nPlomberie Amirale,contact@example.ca\r\n".encode("utf-8"))

    assert headers == ("Entreprise", "Courriel")
    assert rows == [{"Entreprise": "Plomberie Amirale", "Courriel": "contact@example.ca"}]


def test_mapping_requires_business_name_and_distinct_targets() -> None:
    assert _validate_mapping({"Entreprise": "business_name", "Courriel": "email"}) == {
        "Entreprise": "business_name",
        "Courriel": "email",
    }
    with pytest.raises(ValueError, match="Nom établissement"):
        _validate_mapping({"Courriel": "email"})
    with pytest.raises(ValueError, match="mapping"):
        _validate_mapping({"A": "business_name", "B": "business_name"})


async def test_private_temporary_file_store_deletes_partial_oversized_upload(tmp_path) -> None:
    store = LocalTemporaryCsvFileStore(str(tmp_path), max_bytes=4)

    async def chunks() -> AsyncIterator[bytes]:
        yield b"12345"

    with pytest.raises(ValueError, match="dépasse"):
        await store.save(chunks())
    assert list(tmp_path.iterdir()) == []


async def test_private_temporary_file_store_removes_only_expired_csv_files(tmp_path) -> None:
    store = LocalTemporaryCsvFileStore(str(tmp_path), max_bytes=64)
    expired = tmp_path / "expired.csv"
    expired.write_bytes(b"old")
    utime(expired, (time() - 90, time() - 90))
    recent = tmp_path / "recent.csv"
    recent.write_bytes(b"new")
    unrelated = tmp_path / "not-an-import.txt"
    unrelated.write_text("keep", encoding="utf-8")

    removed = await store.cleanup_expired(max_age_seconds=60)

    assert removed == 1
    assert not expired.exists()
    assert recent.exists()
    assert unrelated.exists()
