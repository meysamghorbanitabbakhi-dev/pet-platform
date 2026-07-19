from copy import deepcopy

from app.modules.pet_knowledge.validation import canonical_bytes, validate_bundle


def _bundle() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "dataset_version": "1.0.0",
        "language": "fa-IR",
        "breeds": [
            {
                "id": "dog:poodle",
                "species": "dog",
                "name_fa": "پودل",
                "name_en": "Poodle",
            }
        ],
        "varieties": [
            {
                "id": "dog:poodle:miniature",
                "breed_id": "dog:poodle",
                "name_fa": "پودل مینیاتوری",
                "name_en": "Miniature Poodle",
            }
        ],
        "sources": [
            {
                "id": "source:fci-172",
                "type": "registry_standard",
                "title": "FCI Standard 172",
                "retrieved_at": "2026-07-16",
            }
        ],
        "claims": [
            {
                "id": "claim:poodle-height",
                "breed_id": "dog:poodle",
                "variety_id": "dog:poodle:miniature",
                "claim_type": "height_reference",
                "text_fa": "این بازه یک مرجع نژادی است.",
                "review_status": "veterinary_review_required",
                "source_ids": ["source:fci-172"],
                "app_eligible": False,
                "range": {"min": 28, "max": 35, "unit": "cm"},
            }
        ],
    }


def test_valid_knowledge_bundle_has_deterministic_checksum() -> None:
    bundle = _bundle()
    result = validate_bundle(bundle)
    assert result.valid is True
    assert result.counts == {"breeds": 1, "varieties": 1, "sources": 1, "claims": 1}
    assert canonical_bytes(bundle) == canonical_bytes(deepcopy(bundle))


def test_invalid_cross_references_and_ranges_are_rejected() -> None:
    bundle = _bundle()
    claims = bundle["claims"]
    assert isinstance(claims, list)
    claim = claims[0]
    assert isinstance(claim, dict)
    claim["source_ids"] = ["source:missing"]
    claim["range"] = {"min": 40, "max": 20, "unit": "cm"}
    result = validate_bundle(bundle)
    assert result.valid is False
    assert any(item.startswith("orphan_claim_source") for item in result.errors)
    assert any(item.startswith("reversed_range") for item in result.errors)


def test_submitted_public_flag_is_downgraded_to_warning() -> None:
    bundle = _bundle()
    claims = bundle["claims"]
    assert isinstance(claims, list)
    claim = claims[0]
    assert isinstance(claim, dict)
    claim["app_eligible"] = True
    result = validate_bundle(bundle)
    assert result.valid is True
    assert "app_eligible_forced_false:claim:poodle-height" in result.warnings


def test_collector_retrieval_date_is_accepted_without_legacy_warning() -> None:
    bundle = _bundle()
    sources = bundle["sources"]
    assert isinstance(sources, list)
    source = sources[0]
    assert isinstance(source, dict)
    source.pop("retrieved_at")
    source["retrieval_date"] = "2026-07-16"
    result = validate_bundle(bundle)
    assert result.valid is True
    assert not any(item.startswith("source_missing_retrieved_at") for item in result.warnings)
