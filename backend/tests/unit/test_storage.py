from pathlib import Path

import pytest
from app.integrations.storage.filesystem import LocalFilesystemStorage


@pytest.mark.asyncio
async def test_filesystem_storage_is_atomic_and_scoped(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(tmp_path)
    await storage.ensure_ready()

    result = await storage.put_bytes("pets/abc/photo.jpg", b"pet-photo")

    assert result.key == "pets/abc/photo.jpg"
    assert result.size_bytes == 9
    assert len(result.checksum_sha256) == 64
    assert await storage.exists(result.key)
    assert storage.path_for(result.key).read_bytes() == b"pet-photo"

    await storage.delete(result.key)
    assert not await storage.exists(result.key)


@pytest.mark.parametrize("key", ["", "/etc/passwd", "../secret", "pets/../../secret", "."])
def test_filesystem_storage_rejects_path_traversal(tmp_path: Path, key: str) -> None:
    storage = LocalFilesystemStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.path_for(key)
