import pytest
from app.modules.replenishment.service import assess_reorder, should_break_reorder_snooze


def test_reorder_uses_pessimistic_food_range_and_latest_delivery() -> None:
    result = assess_reorder(
        remaining_low_days=8,
        remaining_high_days=12,
        latest_delivery_days=7,
        safety_buffer_days=2,
    )
    assert result.recommendation == "order_now"
    assert result.risk_gap_days == 1


def test_reorder_does_not_invent_precision_when_portion_is_unknown() -> None:
    result = assess_reorder(
        remaining_low_days=None,
        remaining_high_days=None,
        latest_delivery_days=7,
        safety_buffer_days=2,
    )
    assert result.recommendation == "insufficient_information"
    assert result.risk_gap_days is None


def test_reorder_rejects_invalid_ranges() -> None:
    with pytest.raises(ValueError):
        assess_reorder(
            remaining_low_days=10,
            remaining_high_days=5,
            latest_delivery_days=7,
            safety_buffer_days=2,
        )


def test_reorder_snooze_break_requires_worsening_and_threshold_crossing() -> None:
    assert should_break_reorder_snooze(
        baseline_low_days=19,
        current_low_days=17,
        latest_delivery_days=14,
        safety_buffer_days=3,
        worsening_days=2,
    )
    assert not should_break_reorder_snooze(
        baseline_low_days=18,
        current_low_days=17,
        latest_delivery_days=14,
        safety_buffer_days=3,
        worsening_days=2,
    )
    assert not should_break_reorder_snooze(
        baseline_low_days=22,
        current_low_days=19,
        latest_delivery_days=14,
        safety_buffer_days=3,
        worsening_days=2,
    )
