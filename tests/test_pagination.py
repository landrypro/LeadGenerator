from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.infrastructure.pagination import HmacCursorCodec


def test_signed_cursor_round_trip_and_tampering_rejection() -> None:
    codec = HmacCursorCodec(b"a-test-pagination-key-with-32-bytes-minimum")
    created_at = datetime(2026, 8, 2, 12, tzinfo=UTC)
    item_id = uuid4()

    cursor = codec.encode(created_at, item_id)

    assert codec.decode(cursor) == (created_at, item_id)
    replacement = "A" if cursor[-1] != "A" else "B"
    with pytest.raises(ValueError, match="curseur"):
        codec.decode(f"{cursor[:-1]}{replacement}")


def test_signed_cursor_rejects_invalid_key_naive_date_and_malformed_payload() -> None:
    with pytest.raises(ValueError, match="32 octets"):
        HmacCursorCodec(b"short")

    codec = HmacCursorCodec(b"another-test-pagination-key-with-32-bytes")
    with pytest.raises(ValueError, match="fuseau"):
        codec.encode(datetime(2026, 8, 2, 12), uuid4())
    with pytest.raises(ValueError, match="curseur"):
        codec.decode("not-a-signed-cursor")


def test_signed_cursor_rejects_non_canonical_base64_alias() -> None:
    codec = HmacCursorCodec(b"canonical-pagination-key-with-32-bytes-minimum")
    cursor = codec.encode(datetime(2026, 8, 2, 12, tzinfo=UTC), uuid4())
    payload, signature = cursor.split(".")
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    last_index = alphabet.index(signature[-1])
    alias_index = last_index ^ 1
    aliased_signature = f"{signature[:-1]}{alphabet[alias_index]}"

    # Certaines variantes du dernier caractère décodent vers les mêmes octets
    # lorsque les bits de remplissage ne sont pas vérifiés.
    with pytest.raises(ValueError, match="curseur"):
        codec.decode(f"{payload}.{aliased_signature}")
