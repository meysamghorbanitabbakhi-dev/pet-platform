import pytest
from app.modules.replenishment.service import assess_reorder


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
