from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

from app.modules.pet_knowledge.validation import ValidationResult, validate_bundle


@dataclass(frozen=True, slots=True)
class PackageValidationResult:
    valid: bool
    errors: tuple[str, ...]
    release_checksum: str | None
    bundle: dict[str, Any] | None
    bundle_validation: ValidationResult | None


def validate_collector_archive(path: Path) -> PackageValidationResult:
    errors: list[str] = []
    try:
        archive = ZipFile(path)
    except (BadZipFile, OSError):
        return PackageValidationResult(False, ("invalid_zip_archive",), None, None, None)
    with archive:
        files = [name for name in archive.namelist() if not name.endswith("/")]
        if any(_unsafe_member(name) for name in files):
            return PackageValidationResult(False, ("unsafe_archive_path",), None, None, None)
        manifests = [name for name in files if PurePosixPath(name).name == "release-manifest.json"]
        bundles = [
            name for name in files if PurePosixPath(name).name == "backend-import-bundle.fa.json"
        ]
        if len(manifests) != 1 or len(bundles) != 1:
            return PackageValidationResult(
                False, ("manifest_or_bundle_missing",), None, None, None
            )
        root = str(PurePosixPath(manifests[0]).parent)
        try:
            manifest = json.loads(archive.read(manifests[0]))
            bundle = json.loads(archive.read(bundles[0]))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return PackageValidationResult(False, ("invalid_package_json",), None, None, None)
        entries = manifest.get("files")
        if not isinstance(entries, list):
            return PackageValidationResult(False, ("invalid_manifest_files",), None, None, None)
        entry_names: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("filename"), str):
                errors.append("invalid_manifest_entry")
                continue
            filename = entry["filename"]
            entry_names.add(filename)
            member = f"{root}/{filename}" if root != "." else filename
            try:
                content = archive.read(member)
            except KeyError:
                errors.append(f"manifest_file_missing:{filename}")
                continue
            if entry.get("byte_length") != len(content):
                errors.append(f"manifest_size_mismatch:{filename}")
            if entry.get("sha256") != hashlib.sha256(content).hexdigest():
                errors.append(f"manifest_checksum_mismatch:{filename}")
        actual_names = {
            PurePosixPath(name).name
            for name in files
            if PurePosixPath(name).name != "release-manifest.json"
        }
        if actual_names != entry_names:
            errors.append("manifest_file_set_mismatch")
        canonical = json.dumps(
            entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        expected_release_checksum = "sha256:" + hashlib.sha256(canonical).hexdigest()
        release_checksum = manifest.get("release_checksum")
        if release_checksum != expected_release_checksum:
            errors.append("release_checksum_mismatch")
        bundle_validation = validate_bundle(bundle)
        errors.extend(f"bundle:{error}" for error in bundle_validation.errors)
        return PackageValidationResult(
            not errors,
            tuple(errors),
            release_checksum if isinstance(release_checksum, str) else None,
            bundle,
            bundle_validation,
        )


def _unsafe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return path.is_absolute() or ".." in path.parts or "\\" in name
