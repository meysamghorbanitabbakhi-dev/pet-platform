import pytest
from app.common.phone import normalize_iranian_mobile


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0912 123 4567", "+989121234567"),
        ("+98-912-123-4567", "+989121234567"),
        ("00989121234567", "+989121234567"),
        ("989121234567", "+989121234567"),
        ("9121234567", "+989121234567"),
    ],
)
def test_normalizes_iranian_mobile(raw: str, expected: str) -> None:
    assert normalize_iranian_mobile(raw) == expected


@pytest.mark.parametrize("raw", ["", "02112345678", "+981212345678", "0912123"])
def test_rejects_non_mobile_numbers(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_iranian_mobile(raw)
