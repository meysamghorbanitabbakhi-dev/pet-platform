from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReorderAssessment:
    recommendation: str
    risk_gap_days: int | None
    remaining_low_days: int | None
    remaining_high_days: int | None
    latest_delivery_days: int
    safety_buffer_days: int


def assess_reorder(
    *,
    remaining_low_days: int | None,
    remaining_high_days: int | None,
    latest_delivery_days: int,
    safety_buffer_days: int,
) -> ReorderAssessment:
    if latest_delivery_days < 0 or safety_buffer_days < 0:
        raise ValueError("delivery and safety days cannot be negative")
    if remaining_low_days is None or remaining_high_days is None:
        recommendation = "insufficient_information"
        gap = None
    elif remaining_low_days < 0 or remaining_high_days < remaining_low_days:
        raise ValueError("remaining-food range is invalid")
    else:
        required_days = latest_delivery_days + safety_buffer_days
        gap = required_days - remaining_low_days
        recommendation = "order_now" if gap >= 0 else "not_yet"
    return ReorderAssessment(
        recommendation=recommendation,
        risk_gap_days=gap,
        remaining_low_days=remaining_low_days,
        remaining_high_days=remaining_high_days,
        latest_delivery_days=latest_delivery_days,
        safety_buffer_days=safety_buffer_days,
    )
