import pytest
from app.common.money import Money


def test_money_uses_integer_irr_and_exact_basis_points() -> None:
    merchandise = Money(12_000_000)

    compensation = merchandise.percentage_basis_points(500)

    assert compensation == Money(600_000)
    assert compensation.to_toman_exact() == 60_000


def test_money_rejects_float_and_inexact_toman_conversion() -> None:
    with pytest.raises(TypeError):
        Money(10.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="whole toman"):
        Money(101).to_toman_exact()
