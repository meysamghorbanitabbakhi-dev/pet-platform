import pytest
from app.api.routes.operator import _safe_filename
from fastapi import HTTPException


def test_evidence_filename_is_normalized() -> None:
    assert _safe_filename("supplier assurance 2026.pdf") == "supplier_assurance_2026.pdf"
    assert _safe_filename("../../proof.png") == "proof.png"


def test_empty_evidence_filename_is_rejected() -> None:
    with pytest.raises(HTTPException):
        _safe_filename("...")
