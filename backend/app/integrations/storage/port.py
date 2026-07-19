from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size_bytes: int
    checksum_sha256: str


class ObjectStorage(Protocol):
    async def ensure_ready(self) -> None: ...

    async def put_bytes(self, key: str, content: bytes) -> StoredObject: ...

    async def exists(self, key: str) -> bool: ...

    async def delete(self, key: str) -> None: ...
