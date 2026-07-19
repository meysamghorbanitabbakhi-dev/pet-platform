from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BenchmarkInput:
    value: Decimal
    unit: str
    measured_on: date
    pet_birth_date: date | None
    pet_birth_date_precision: str | None
    pet_sex: str | None
    pet_neuter_status: str | None
    pet_breed_id: str | None
    pet_variety_id: str | None
    pet_mixed_breed: bool


@dataclass(frozen=True, slots=True)
class BenchmarkRule:
    unit: str
    breed_id: str
    variety_id: str | None
    minimum: Decimal
    maximum: Decimal
    minimum_age_days: int | None
    maximum_age_days: int | None
    sex_scope: str
    neuter_scope: str
    comparison_allowed: bool
    reference_purpose: str


def evaluate_benchmark(value: BenchmarkInput, rule: BenchmarkRule) -> dict[str, object]:
    reasons: list[str] = []
    normalized = _normalize(value.value, value.unit, rule.unit)
    if normalized is None:
        reasons.append("unit_not_compatible")
    if value.pet_mixed_breed:
        reasons.append("mixed_breed_requires_individual_interpretation")
    if value.pet_breed_id != rule.breed_id:
        reasons.append("breed_not_applicable")
    if rule.variety_id is not None and value.pet_variety_id != rule.variety_id:
        reasons.append("variety_not_applicable")
    if rule.sex_scope != "combined" and value.pet_sex != rule.sex_scope:
        reasons.append("sex_not_applicable")
    if rule.neuter_scope != "any" and value.pet_neuter_status != rule.neuter_scope:
        reasons.append("neuter_status_not_applicable")
    age_days: int | None = None
    if rule.minimum_age_days is not None or rule.maximum_age_days is not None:
        if value.pet_birth_date is None or value.pet_birth_date_precision not in {"exact", "month"}:
            reasons.append("age_not_precise_enough")
        else:
            age_days = (value.measured_on - value.pet_birth_date).days
            if age_days < 0:
                reasons.append("measurement_precedes_birth")
            if rule.minimum_age_days is not None and age_days < rule.minimum_age_days:
                reasons.append("younger_than_reference_scope")
            if rule.maximum_age_days is not None and age_days > rule.maximum_age_days:
                reasons.append("older_than_reference_scope")
    if reasons:
        return {
            "state": "not_applicable",
            "reasons": reasons,
            "classification": None,
            "age_days": age_days,
        }
    if not rule.comparison_allowed:
        return {
            "state": "reference_only",
            "reasons": ["comparison_not_approved"],
            "classification": None,
            "age_days": age_days,
        }
    assert normalized is not None
    if normalized < rule.minimum:
        classification = "below_reference"
    elif normalized > rule.maximum:
        classification = "above_reference"
    else:
        classification = "within_reference"
    return {
        "state": "compared",
        "reasons": [],
        "classification": classification,
        "normalized_value": float(normalized),
        "age_days": age_days,
        "interpretation": "non_diagnostic_population_reference",
    }


def _normalize(value: Decimal, source_unit: str, target_unit: str) -> Decimal | None:
    if source_unit == target_unit:
        return value
    if source_unit == "g" and target_unit == "kg":
        return value / Decimal(1000)
    return None
