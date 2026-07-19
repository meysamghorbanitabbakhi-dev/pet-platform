from uuid import uuid4

import pytest
from app.core.config import Settings
from app.integrations.otp.dev_console import ConsoleOtpProvider
from app.integrations.otp.factory import OtpProviderNotConfiguredError, build_otp_provider
from app.integrations.otp.payamak_panel import PayamakPanelOtpProvider
from app.modules.identity.models import OtpChallenge
from app.modules.identity.otp import generate_otp_code, hash_otp_code, otp_matches
from pydantic import ValidationError


def test_generated_otp_is_six_numeric_digits() -> None:
    code = generate_otp_code()

    assert len(code) == 6
    assert code.isdigit()


def test_otp_hash_is_bound_to_challenge_and_mobile() -> None:
    challenge_id = uuid4()
    mobile = "+989121234567"
    code = "483920"
    challenge = OtpChallenge(
        id=challenge_id,
        mobile_e164=mobile,
        code_hash=hash_otp_code(
            pepper="a-secure-test-pepper-that-is-long-enough",
            challenge_id=challenge_id,
            mobile_e164=mobile,
            code=code,
        ),
        delivery_status="sent",
        attempts=0,
        max_attempts=5,
    )

    assert otp_matches(
        pepper="a-secure-test-pepper-that-is-long-enough",
        challenge=challenge,
        candidate_code=code,
    )
    assert not otp_matches(
        pepper="a-secure-test-pepper-that-is-long-enough",
        challenge=challenge,
        candidate_code="000000",
    )


def _unconfigured(**overrides: object) -> Settings:
    # Settings() reads ambient env vars by default; tests must pin the fields
    # under test explicitly rather than relying on the environment (which,
    # e.g. under `docker run --env-file .env.example`, sets these to empty
    # strings, not None) to be "unconfigured".
    return Settings(
        payamak_panel_username=None,
        payamak_panel_password=None,
        payamak_panel_sender_number=None,
        **overrides,
    )


def test_otp_provider_fails_closed_without_configuration_or_fallback() -> None:
    settings = _unconfigured(app_env="development", otp_dev_console_fallback_enabled=False)

    with pytest.raises(OtpProviderNotConfiguredError):
        build_otp_provider(settings)


def test_blank_payamak_credentials_are_treated_as_unconfigured() -> None:
    # .env.example ships PAYAMAK_PANEL_* as empty strings (not unset) as
    # placeholders; compose's env_file merge loads that literally, so this
    # must fall back the same as a truly-unset provider, not attempt a real
    # network call with blank credentials.
    settings = Settings(
        payamak_panel_username="",
        payamak_panel_password="",
        payamak_panel_sender_number="  ",
        app_env="development",
        otp_dev_console_fallback_enabled=True,
    )

    assert isinstance(build_otp_provider(settings), ConsoleOtpProvider)


def test_otp_dev_console_fallback_only_used_when_no_real_provider_configured() -> None:
    settings = _unconfigured(app_env="development", otp_dev_console_fallback_enabled=True)

    assert isinstance(build_otp_provider(settings), ConsoleOtpProvider)


def test_real_provider_takes_precedence_over_dev_console_fallback() -> None:
    settings = Settings(
        app_env="development",
        otp_dev_console_fallback_enabled=True,
        payamak_panel_username="user",
        payamak_panel_password="pass",
        payamak_panel_sender_number="10001234",
    )

    assert isinstance(build_otp_provider(settings), PayamakPanelOtpProvider)


def test_otp_dev_console_fallback_can_never_be_enabled_in_production() -> None:
    with pytest.raises(ValidationError, match="otp_dev_console_fallback_enabled"):
        Settings(
            app_env="production",
            otp_dev_console_fallback_enabled=True,
            jwt_secret="a" * 32,
            webhook_secret="b" * 32,
            otp_pepper="c" * 32,
            metrics_bearer_token="d" * 32,
        )
