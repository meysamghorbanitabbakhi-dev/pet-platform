from __future__ import annotations

import re
from pathlib import Path

from app.core.config import Settings

_ENV_EXAMPLE_PATH = Path(__file__).resolve().parents[2] / ".env.example"
_KEY_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=")


def _env_example_keys() -> set[str]:
    keys: set[str] = set()
    for line in _ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _KEY_PATTERN.match(stripped)
        if match:
            keys.add(match.group(1))
    return keys


def test_every_env_example_key_matches_a_real_settings_field() -> None:
    """pydantic-settings' default env-var name for a field is just its
    uppercased name (case_sensitive=False), and Settings.model_config sets
    extra="ignore" -- meaning a typo'd or renamed key in .env.example is
    never rejected at startup, it is silently ignored, and the
    application quietly falls back to that field's Python default with
    no error or warning. This test exists because that exact class of bug
    was found for real: .env.example documented LATE_COMPENSATION_
    BASIS_POINTS and WALLET_CREDIT_EXPIRY_MONTHS, which do not correspond
    to any Settings field (the real names are LATE_CREDIT_BASIS_POINTS /
    LATE_CREDIT_EXPIRY_MONTHS) -- an operator following this file to
    configure the late-credit policy before enabling late_credit_enabled
    would have silently gotten the code defaults regardless of what they
    set, with nothing here to catch it."""
    expected_names = {name.upper() for name in Settings.model_fields}
    unmatched = _env_example_keys() - expected_names
    assert not unmatched, (
        f".env.example has keys with no matching Settings field: {sorted(unmatched)} "
        "-- these are silently ignored (extra='ignore'), not rejected"
    )
