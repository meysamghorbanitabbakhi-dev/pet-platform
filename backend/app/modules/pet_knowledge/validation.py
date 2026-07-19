from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationResult:
    checksum_sha256: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    counts: dict[str, int]

    @property
    def valid(self) -> bool:
        return not self.errors


def canonical_bytes(bundle: dict[str, Any]) -> bytes:
    return json.dumps(
        bundle, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def validate_bundle(bundle: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    for field in ("schema_version", "dataset_version", "language"):
        if not isinstance(bundle.get(field), str) or not bundle[field].strip():
            errors.append(f"missing_or_invalid:{field}")
    if bundle.get("language") != "fa-IR":
        errors.append("unsupported_language")
    collections: dict[str, list[dict[str, Any]]] = {}
    for name in ("breeds", "varieties", "sources", "claims"):
        value = bundle.get(name)
        if not isinstance(value, list):
            errors.append(f"missing_or_invalid:{name}")
            collections[name] = []
        elif not all(isinstance(item, dict) for item in value):
            errors.append(f"invalid_item:{name}")
            collections[name] = [item for item in value if isinstance(item, dict)]
        else:
            collections[name] = value

    ids: dict[str, set[str]] = {}
    for name, records in collections.items():
        values: list[str] = []
        for index, record in enumerate(records):
            external_id = record.get("id")
            if not isinstance(external_id, str) or not external_id:
                errors.append(f"missing_id:{name}:{index}")
                continue
            values.append(external_id)
        duplicates = {value for value in values if values.count(value) > 1}
        errors.extend(f"duplicate_id:{name}:{value}" for value in sorted(duplicates))
        ids[name] = set(values)

    for record in collections["breeds"]:
        breed_id = record.get("id", "unknown")
        if record.get("species") not in {"dog", "cat"}:
            errors.append(f"invalid_species:{breed_id}")
        for field in ("name_fa", "name_en"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                errors.append(f"missing_field:breeds:{breed_id}:{field}")
        if isinstance(breed_id, str) and not re.fullmatch(r"(dog|cat):[a-z0-9-]+", breed_id):
            errors.append(f"invalid_breed_id:{breed_id}")

    for record in collections["varieties"]:
        variety_id = record.get("id", "unknown")
        breed_id = record.get("breed_id")
        if breed_id not in ids["breeds"]:
            errors.append(f"orphan_variety_breed:{variety_id}:{breed_id}")
        for field in ("name_fa", "name_en"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                errors.append(f"missing_field:varieties:{variety_id}:{field}")

    variety_breeds = {
        record.get("id"): record.get("breed_id") for record in collections["varieties"]
    }

    for record in collections["sources"]:
        source_id = record.get("id", "unknown")
        for field in ("type", "title"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                errors.append(f"missing_field:sources:{source_id}:{field}")
        if not (record.get("retrieved_at") or record.get("retrieval_date")):
            warnings.append(f"source_missing_retrieved_at:{source_id}")

    for record in collections["claims"]:
        claim_id = record.get("id", "unknown")
        breed_id = record.get("breed_id")
        variety_id = record.get("variety_id")
        if breed_id not in ids["breeds"]:
            errors.append(f"orphan_claim_breed:{claim_id}:{breed_id}")
        if variety_id is not None and variety_id not in ids["varieties"]:
            errors.append(f"orphan_claim_variety:{claim_id}:{variety_id}")
        elif variety_id is not None and variety_breeds.get(variety_id) != breed_id:
            errors.append(f"claim_variety_breed_mismatch:{claim_id}:{variety_id}")
        source_ids = record.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids:
            errors.append(f"claim_without_sources:{claim_id}")
        else:
            if any(not isinstance(source_id, str) for source_id in source_ids):
                errors.append(f"invalid_claim_source_id:{claim_id}")
                source_ids = [source_id for source_id in source_ids if isinstance(source_id, str)]
            if len(source_ids) != len(set(source_ids)):
                errors.append(f"duplicate_claim_source:{claim_id}")
            for source_id in source_ids:
                if source_id not in ids["sources"]:
                    errors.append(f"orphan_claim_source:{claim_id}:{source_id}")
        for field in ("claim_type", "text_fa", "review_status"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                errors.append(f"missing_field:claims:{claim_id}:{field}")
        if record.get("review_status") not in {
            "draft",
            "editorial_reviewed",
            "veterinary_review_required",
            "veterinary_approved",
            "rejected",
            "superseded",
            "withdrawn",
        }:
            errors.append(f"invalid_review_status:{claim_id}")
        if record.get("app_eligible") is True:
            warnings.append(f"app_eligible_forced_false:{claim_id}")

    for collection_name, records in collections.items():
        for record in records:
            _validate_ranges(record, f"{collection_name}:{record.get('id', 'unknown')}", errors)

    counts = {name: len(records) for name, records in collections.items()}
    return ValidationResult(
        checksum_sha256=hashlib.sha256(canonical_bytes(bundle)).hexdigest(),
        errors=tuple(sorted(set(errors))),
        warnings=tuple(sorted(set(warnings))),
        counts=counts,
    )


def _validate_ranges(value: object, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        minimum = value.get("min")
        maximum = value.get("max")
        if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)):
            if minimum < 0 or maximum < 0:
                errors.append(f"negative_range:{path}")
            if minimum > maximum:
                errors.append(f"reversed_range:{path}")
        for key, nested in value.items():
            _validate_ranges(nested, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_ranges(nested, f"{path}[{index}]", errors)
