from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import Settings
from app.main import create_app

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
BACKEND_DIR = Path(__file__).resolve().parents[2]
MANIFEST_PATH = BACKEND_DIR / "release-contract.json"


def canonical_openapi() -> tuple[dict[str, Any], bytes]:
    document = create_app().openapi()
    raw = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    return document, raw


def actual_heads() -> list[str]:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return sorted(ScriptDirectory.from_config(config).get_heads())


def property_schema(schemas: dict[str, Any], qualified: str) -> dict[str, Any] | None:
    schema_name, property_name = qualified.split(".", 1)
    value = schemas.get(schema_name, {}).get("properties", {}).get(property_name)
    return value if isinstance(value, dict) else None


def enum_values(prop: dict[str, Any] | None) -> set[Any]:
    if not prop:
        return set()
    entries = [prop, *prop.get("anyOf", []), *prop.get("oneOf", [])]
    return {value for entry in entries for value in entry.get("enum", [])}


def has_constant(prop: dict[str, Any] | None, value: Any) -> bool:
    if not prop:
        return False
    return any(
        entry.get("const") == value
        for entry in [prop, *prop.get("anyOf", []), *prop.get("oneOf", [])]
    )


def verify(manifest: dict[str, Any], document: dict[str, Any], raw: bytes) -> list[str]:
    differences: list[str] = []
    heads = actual_heads()
    expected_heads = manifest["alembic"]["heads"]
    if len(heads) != 1:
        differences.append(f"Alembic must have exactly one head; actual={heads}")
    if heads != expected_heads:
        differences.append(f"Alembic heads expected={expected_heads} actual={heads}")

    contract = manifest["openapi"]
    paths = document.get("paths", {})
    schemas = document.get("components", {}).get("schemas", {})
    operations = {
        (method.upper(), path)
        for path, item in paths.items()
        for method in item
        if method in HTTP_METHODS
    }
    facts = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "path_count": len(paths),
        "operation_count": len(operations),
        "schema_count": len(schemas),
    }
    for key, actual in facts.items():
        if contract[key] != actual:
            differences.append(f"OpenAPI {key} expected={contract[key]!r} actual={actual!r}")
    for method, path in contract["required_operations"]:
        if (method, path) not in operations:
            differences.append(f"missing required operation {method} {path}")
    for name, properties in contract["required_schema_properties"].items():
        if name not in schemas:
            differences.append(f"missing required schema {name}")
            continue
        for prop in properties:
            if prop not in schemas[name].get("properties", {}):
                differences.append(f"schema {name} missing property {prop}")
    for qualified, expected in contract["required_enums"].items():
        missing = set(expected) - enum_values(property_schema(schemas, qualified))
        if missing:
            differences.append(f"{qualified} enum missing {sorted(missing)}")
    for qualified, expected in contract["required_patterns"].items():
        actual = (property_schema(schemas, qualified) or {}).get("pattern")
        if actual != expected:
            differences.append(f"{qualified} pattern expected={expected!r} actual={actual!r}")
    for qualified, expected in contract["required_constants"].items():
        if not has_constant(property_schema(schemas, qualified), expected):
            differences.append(f"{qualified} constant expected={expected!r}")

    for name, expected in manifest["policy_defaults"].items():
        field = Settings.model_fields.get(name)
        actual = field.default if field is not None else None
        if field is None or actual != expected:
            differences.append(f"Settings.{name} default expected={expected!r} actual={actual!r}")
    for path in (BACKEND_DIR / "openapi.json", BACKEND_DIR / "docs/api/openapi.json"):
        if not path.exists():
            differences.append(f"missing generated OpenAPI file {path.relative_to(BACKEND_DIR)}")
        elif path.read_bytes() != raw:
            differences.append(f"generated OpenAPI drift in {path.relative_to(BACKEND_DIR)}")
    return differences


def write_derived(manifest: dict[str, Any], document: dict[str, Any], raw: bytes) -> None:
    paths = document.get("paths", {})
    schemas = document.get("components", {}).get("schemas", {})
    operation_count = sum(method in HTTP_METHODS for item in paths.values() for method in item)
    manifest["alembic"]["heads"] = actual_heads()
    manifest["openapi"].update(
        sha256=hashlib.sha256(raw).hexdigest(),
        path_count=len(paths),
        operation_count=operation_count,
        schema_count=len(schemas),
    )
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the canonical release contract")
    parser.add_argument("--write", action="store_true", help="refresh derived facts only")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    document, raw = canonical_openapi()
    if args.write:
        write_derived(manifest, document, raw)
        print(f"release_contract_updated path={MANIFEST_PATH}")
        return
    differences = verify(manifest, document, raw)
    if differences:
        print("RELEASE CONTRACT BLOCKED")
        for difference in differences:
            print(f"- {difference}")
        raise SystemExit(1)
    print("release_contract_verified")


if __name__ == "__main__":
    main()
