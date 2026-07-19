from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from pathlib import Path, PurePosixPath

from app.integrations.storage.port import StoredObject


class LocalFilesystemStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    async def ensure_ready(self) -> None:
        await asyncio.to_thread(self._ensure_ready_sync)

    def _ensure_ready_sync(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        probe = self._root / ".readiness"
        probe.touch(exist_ok=True)
        probe.unlink(missing_ok=True)

    def path_for(self, key: str) -> Path:
        normalized = PurePosixPath(key)
        if (
            not key
            or not normalized.parts
            or normalized.is_absolute()
            or ".." in normalized.parts
            or "." in normalized.parts
        ):
            raise ValueError("storage key must be a safe relative POSIX path")
        path = (self._root / Path(*normalized.parts)).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("storage key escapes media root")
        return path

    async def put_bytes(self, key: str, content: bytes) -> StoredObject:
        return await asyncio.to_thread(self._put_bytes_sync, key, content)

    def _put_bytes_sync(self, key: str, content: bytes) -> StoredObject:
        target = self.path_for(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        checksum = hashlib.sha256(content).hexdigest()
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_name = temporary.name
            os.replace(temporary_name, target)
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
        return StoredObject(key=key, size_bytes=len(content), checksum_sha256=checksum)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self.path_for(key).is_file)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.path_for(key).unlink, missing_ok=True)
