from datetime import UTC, datetime

import pytest
from app.api.routes.pet_assets import BodyAssessmentBody, _matches_signature, _safe_filename
from pydantic import ValidationError


def test_pet_asset_signature_matching_rejects_spoofed_content() -> None:
    assert _matches_signature(b"%PDF-1.7 example", "application/pdf") is True
    assert _matches_signature(b"not a pdf", "application/pdf") is False
    assert _matches_signature(b"\x89PNG\r\n\x1a\nrest", "image/png") is True
    assert _matches_signature(b"\xff\xd8\xffrest", "image/jpeg") is True


def test_pet_asset_filename_cannot_escape_storage_boundary() -> None:
    assert _safe_filename("../../medical report.pdf") == "medical_report.pdf"
    assert _safe_filename("..\\..\\body.jpg") == "body.jpg"


def test_body_assessment_uses_nine_point_scale() -> None:
    assessment = BodyAssessmentBody(
        bcs_score=5,
        bcs_scale=9,
        muscle_condition="normal",
        answers={"ribs_felt": "easily"},
        assessed_at=datetime(2026, 7, 16, tzinfo=UTC),
    )
    assert assessment.bcs_score == 5
    with pytest.raises(ValidationError):
        BodyAssessmentBody(
            bcs_score=5,
            bcs_scale=5,
            muscle_condition="normal",
            answers={},
            assessed_at=datetime(2026, 7, 16, tzinfo=UTC),
        )
