from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the deterministic OpenAPI contract")
    parser.add_argument("--output", default="docs/api/openapi.json")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"openapi_exported path={output}")


if __name__ == "__main__":
    main()
