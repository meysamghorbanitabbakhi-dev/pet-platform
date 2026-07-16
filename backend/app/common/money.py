from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Money:
    """Integer IRR amount. Floating-point money is intentionally unsupported."""

    amount_irr: int

    def __post_init__(self) -> None:
        if isinstance(self.amount_irr, bool) or not isinstance(self.amount_irr, int):
            raise TypeError("amount_irr must be an integer")

    def __add__(self, other: Money) -> Money:
        return Money(self.amount_irr + other.amount_irr)

    def __sub__(self, other: Money) -> Money:
        return Money(self.amount_irr - other.amount_irr)

    def percentage_basis_points(self, basis_points: int) -> Money:
        if not 0 <= basis_points <= 10_000:
            raise ValueError("basis_points must be between 0 and 10,000")
        return Money((self.amount_irr * basis_points) // 10_000)

    def to_toman_exact(self) -> int:
        quotient, remainder = divmod(self.amount_irr, 10)
        if remainder:
            raise ValueError("IRR amount cannot be represented as a whole toman amount")
        return quotient
