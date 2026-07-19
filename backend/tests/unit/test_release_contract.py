from __future__ import annotations

import copy
import json

import pytest
from app.cli import verify_release_contract as verifier


@pytest.fixture
def contract_inputs() -> tuple[dict[str, object], dict[str, object], bytes]:
    manifest = json.loads(verifier.MANIFEST_PATH.read_text(encoding="utf-8"))
    document, raw = verifier.canonical_openapi()
    return manifest, document, raw


def test_release_contract_reports_missing_revision(
    monkeypatch: pytest.MonkeyPatch,
    contract_inputs: tuple[dict[str, object], dict[str, object], bytes],
) -> None:
    manifest, document, raw = contract_inputs
    monkeypatch.setattr(verifier, "actual_heads", lambda: ["missing"])
    assert any("Alembic heads" in item for item in verifier.verify(manifest, document, raw))


def test_release_contract_rejects_multiple_heads(
    monkeypatch: pytest.MonkeyPatch,
    contract_inputs: tuple[dict[str, object], dict[str, object], bytes],
) -> None:
    manifest, document, raw = contract_inputs
    monkeypatch.setattr(verifier, "actual_heads", lambda: ["a", "b"])
    assert any("exactly one head" in item for item in verifier.verify(manifest, document, raw))


def test_release_contract_reports_hash_drift(
    contract_inputs: tuple[dict[str, object], dict[str, object], bytes],
) -> None:
    manifest, document, raw = contract_inputs
    assert any("sha256" in item for item in verifier.verify(manifest, document, raw + b" "))


def test_release_contract_reports_policy_drift(
    contract_inputs: tuple[dict[str, object], dict[str, object], bytes],
) -> None:
    manifest, document, raw = contract_inputs
    changed = copy.deepcopy(manifest)
    changed["policy_defaults"]["full_payment_only"] = False
    assert any("full_payment_only" in item for item in verifier.verify(changed, document, raw))


def test_release_contract_reports_missing_required_operation(
    contract_inputs: tuple[dict[str, object], dict[str, object], bytes],
) -> None:
    manifest, document, raw = contract_inputs
    changed = copy.deepcopy(manifest)
    changed["openapi"]["required_operations"].append(["DELETE", "/not-present"])
    assert any("DELETE /not-present" in item for item in verifier.verify(changed, document, raw))
