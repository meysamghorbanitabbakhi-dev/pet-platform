from datetime import UTC, date, datetime, timedelta

import pytest
from app.api.routes.pet_health import GuidancePreferenceBody
from app.modules.pet_knowledge.guidance import guidance_age_applicable
from pydantic import ValidationError


def test_guidance_without_declared_age_scope_is_generally_applicable() -> None:
    assert guidance_age_applicable({}, None, date(2026, 7, 16)) is True


def test_guidance_with_age_scope_fails_closed_without_birth_date() -> None:
    assert (
        guidance_age_applicable(
            {"minimum_age_days": 365}, None, date(2026, 7, 16)
        )
        is False
    )


def test_guidance_age_scope_uses_explicit_day_boundaries() -> None:
    record = {"minimum_age_days": 100, "maximum_age_days": 200}
    assert guidance_age_applicable(record, date(2026, 3, 1), date(2026, 7, 16)) is True
    assert guidance_age_applicable(record, date(2026, 7, 1), date(2026, 7, 16)) is False


def test_snooze_requires_timestamp_and_dismiss_rejects_it() -> None:
    with pytest.raises(ValidationError):
        GuidancePreferenceBody(action="snooze")
    with pytest.raises(ValidationError):
        GuidancePreferenceBody(
            action="dismiss",
            snoozed_until=datetime.now(UTC) + timedelta(days=1),
        )
