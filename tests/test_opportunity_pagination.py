from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from backend.app.infrastructure.opportunity_pagination import HmacOpportunityCursorCodec, OpportunityCursor


def test_opportunity_cursor_is_signed_canonical_and_bound_to_its_filters() -> None:
    codec = HmacOpportunityCursorCodec(b"opportunity-pagination-key-with-at-least-32-bytes")
    expected = OpportunityCursor(date(2026, 10, 15), datetime(2026, 9, 10, 12, tzinfo=UTC), uuid4())

    token = codec.encode(expected, scope="organization-and-filters")

    assert codec.decode(token, scope="organization-and-filters") == expected
    with pytest.raises(ValueError, match="curseur"):
        codec.decode(token, scope="another-organization-or-filter")
    with pytest.raises(ValueError, match="curseur"):
        codec.decode(f"{token[:-1]}{'A' if token[-1] != 'A' else 'B'}", scope="organization-and-filters")
