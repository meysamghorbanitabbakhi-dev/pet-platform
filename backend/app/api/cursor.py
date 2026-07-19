from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CursorPosition:
    created_at: datetime
    item_id: UUID


class CursorError(ValueError):
    pass


def encode_cursor(position: CursorPosition, secret: str) -> str:
    payload = json.dumps(
        {"created_at": position.created_at.isoformat(), "id": str(position.item_id)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + signature).decode().rstrip("=")


def decode_cursor(value: str, secret: str) -> CursorPosition:
    try:
        padded = value + "=" * (-len(value) % 4)
        combined = base64.urlsafe_b64decode(padded.encode())
        payload, supplied_signature = combined[:-32], combined[-32:]
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied_signature, expected):
            raise CursorError("invalid_cursor")
        parsed = json.loads(payload)
        return CursorPosition(
            created_at=datetime.fromisoformat(parsed["created_at"]),
            item_id=UUID(parsed["id"]),
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        if isinstance(exc, CursorError):
            raise
        raise CursorError("invalid_cursor") from exc


def cursor_page(items: Sequence[object], *, next_cursor: str | None) -> dict[str, object]:
    return {
        "items": items,
        "page": {"next_cursor": next_cursor, "has_more": next_cursor is not None},
    }
