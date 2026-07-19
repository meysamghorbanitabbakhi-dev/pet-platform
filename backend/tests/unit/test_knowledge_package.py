import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.modules.pet_knowledge.package import validate_collector_archive


def test_collector_archive_manifest_and_bundle_are_verified(tmp_path: Path) -> None:
    bundle = {
        "schema_version": "1.0.0",
        "dataset_version": "test",
        "language": "fa-IR",
        "breeds": [],
        "varieties": [],
        "sources": [],
        "claims": [],
    }
    bundle_bytes = json.dumps(bundle, ensure_ascii=False).encode()
    files = [
        {
            "filename": "backend-import-bundle.fa.json",
            "byte_length": len(bundle_bytes),
            "sha256": hashlib.sha256(bundle_bytes).hexdigest(),
        }
    ]
    canonical = json.dumps(
        files, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    manifest = {
        "files": files,
        "release_checksum": "sha256:" + hashlib.sha256(canonical).hexdigest(),
    }
    archive = tmp_path / "knowledge.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as output:
        output.writestr("package/backend-import-bundle.fa.json", bundle_bytes)
        output.writestr("package/release-manifest.json", json.dumps(manifest))
    result = validate_collector_archive(archive)
    assert result.valid is True
    assert result.bundle_validation is not None
    assert result.bundle_validation.counts["breeds"] == 0


def test_collector_archive_rejects_manifest_tampering(tmp_path: Path) -> None:
    archive = tmp_path / "knowledge.zip"
    files = [
        {
            "filename": "backend-import-bundle.fa.json",
            "byte_length": 1,
            "sha256": "0" * 64,
        }
    ]
    manifest = {"files": files, "release_checksum": "sha256:" + "0" * 64}
    with ZipFile(archive, "w", ZIP_DEFLATED) as output:
        output.writestr("package/backend-import-bundle.fa.json", "{}")
        output.writestr("package/release-manifest.json", json.dumps(manifest))
    result = validate_collector_archive(archive)
    assert result.valid is False
    assert "manifest_size_mismatch:backend-import-bundle.fa.json" in result.errors
