from datetime import UTC, datetime
from uuid import UUID

import pytest
from app.api.cursor import CursorError, CursorPosition, decode_cursor, encode_cursor


def test_cursor_round_trip_is_opaque_and_stable() -> None:
    position = CursorPosition(
        datetime(2026, 7, 16, 12, 30, tzinfo=UTC),
        UUID("10000000-0000-4000-8000-000000000001"),
    )
    encoded = encode_cursor(position, "s" * 32)
    assert decode_cursor(encoded, "s" * 32) == position


def test_cursor_rejects_tampering_and_wrong_secret() -> None:
    position = CursorPosition(
        datetime(2026, 7, 16, 12, 30, tzinfo=UTC),
        UUID("10000000-0000-4000-8000-000000000001"),
    )
    encoded = encode_cursor(position, "s" * 32)
    with pytest.raises(CursorError):
        decode_cursor(encoded, "different-secret-that-is-long-enough")
    midpoint = len(encoded) // 2
    replacement = "A" if encoded[midpoint] != "A" else "B"
    tampered = encoded[:midpoint] + replacement + encoded[midpoint + 1 :]
    with pytest.raises(CursorError):
        decode_cursor(tampered, "s" * 32)
