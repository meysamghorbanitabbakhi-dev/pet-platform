from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.modules.pet_knowledge.package import validate_collector_archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a collector knowledge ZIP package")
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    result = validate_collector_archive(args.archive)
    print(
        json.dumps(
            {
                "valid": result.valid,
                "release_checksum": result.release_checksum,
                "bundle_checksum": (
                    result.bundle_validation.checksum_sha256
                    if result.bundle_validation is not None
                    else None
                ),
                "counts": (
                    result.bundle_validation.counts
                    if result.bundle_validation is not None
                    else None
                ),
                "warnings": (
                    list(result.bundle_validation.warnings)
                    if result.bundle_validation is not None
                    else []
                ),
                "errors": list(result.errors),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not result.valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
