from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from app.api.routes.pet_health import MeasurementBody, _weight_kg
from app.modules.pet_health.benchmarks import BenchmarkInput, BenchmarkRule, evaluate_benchmark
from app.modules.pet_health.models import HealthMeasurement
from pydantic import ValidationError


def test_measurement_contract_accepts_supported_unit() -> None:
    body = MeasurementBody(
        measurement_type="weight",
        value=Decimal("4.250"),
        unit="kg",
        measured_at=datetime(2026, 7, 16, tzinfo=UTC),
        source="owner_reported",
    )
    assert body.value == Decimal("4.250")


def test_measurement_contract_rejects_wrong_unit_for_type() -> None:
    with pytest.raises(ValidationError):
        MeasurementBody(
            measurement_type="weight",
            value=Decimal("4.250"),
            unit="cm",
            measured_at=datetime(2026, 7, 16, tzinfo=UTC),
            source="owner_reported",
        )


def test_weight_normalizes_grams_without_losing_precision() -> None:
    measurement = HealthMeasurement(
        pet_id=uuid4(),
        measurement_type="weight",
        value=Decimal("4250"),
        unit="g",
        measured_at=datetime(2026, 7, 16, tzinfo=UTC),
        source="owner_reported",
        entered_by_identity_id=uuid4(),
        confidence="medium",
        status="active",
    )
    assert _weight_kg(measurement) == Decimal("4.25")


def _benchmark_input(**overrides: object) -> BenchmarkInput:
    values: dict[str, object] = {
        "value": Decimal("4.2"),
        "unit": "kg",
        "measured_on": datetime(2026, 7, 16, tzinfo=UTC).date(),
        "pet_birth_date": datetime(2025, 7, 16, tzinfo=UTC).date(),
        "pet_birth_date_precision": "exact",
        "pet_sex": "male",
        "pet_neuter_status": "intact",
        "pet_breed_id": "dog:poodle",
        "pet_variety_id": "dog:poodle:miniature",
        "pet_mixed_breed": False,
    }
    values.update(overrides)
    return BenchmarkInput(**values)  # type: ignore[arg-type]


def _benchmark_rule(**overrides: object) -> BenchmarkRule:
    values: dict[str, object] = {
        "unit": "kg",
        "breed_id": "dog:poodle",
        "variety_id": "dog:poodle:miniature",
        "minimum": Decimal("4.0"),
        "maximum": Decimal("6.0"),
        "minimum_age_days": 300,
        "maximum_age_days": 800,
        "sex_scope": "combined",
        "neuter_scope": "any",
        "comparison_allowed": True,
        "reference_purpose": "population_reference",
    }
    values.update(overrides)
    return BenchmarkRule(**values)  # type: ignore[arg-type]


def test_approved_applicable_benchmark_is_non_diagnostic_comparison() -> None:
    result = evaluate_benchmark(_benchmark_input(), _benchmark_rule())
    assert result["state"] == "compared"
    assert result["classification"] == "within_reference"
    assert result["interpretation"] == "non_diagnostic_population_reference"


def test_registry_reference_never_classifies_when_comparison_disabled() -> None:
    result = evaluate_benchmark(
        _benchmark_input(),
        _benchmark_rule(
            comparison_allowed=False, reference_purpose="registry_conformation"
        ),
    )
    assert result["state"] == "reference_only"
    assert result["classification"] is None


def test_benchmark_fails_closed_for_imprecise_age() -> None:
    result = evaluate_benchmark(
        _benchmark_input(pet_birth_date_precision="estimated"), _benchmark_rule()
    )
    assert result["state"] == "not_applicable"
    assert "age_not_precise_enough" in result["reasons"]


def test_mixed_breed_is_not_classified_by_single_breed_reference() -> None:
    result = evaluate_benchmark(_benchmark_input(pet_mixed_breed=True), _benchmark_rule())
    assert result["state"] == "not_applicable"
    assert "mixed_breed_requires_individual_interpretation" in result["reasons"]
