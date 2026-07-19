from app.core.config import Settings
from app.integrations.otp.dev_console import ConsoleOtpProvider
from app.integrations.otp.payamak_panel import PayamakPanelConfig, PayamakPanelOtpProvider


class OtpProviderNotConfiguredError(Exception):
    pass


def build_otp_provider(settings: Settings) -> PayamakPanelOtpProvider | ConsoleOtpProvider:
    # .env.example ships with these blank (empty string, not unset) as
    # placeholders for real credentials; compose's env_file merge loads that
    # literally, so "" must be treated the same as unconfigured, not as a
    # real (blank) username/password to send to Payamak Panel.
    username = (settings.payamak_panel_username or "").strip() or None
    password = (settings.payamak_panel_password or "").strip() or None
    sender_number = (settings.payamak_panel_sender_number or "").strip() or None
    if username is None or password is None or sender_number is None:
        # otp_dev_console_fallback_enabled can never be true in production
        # (enforced by Settings.validate_production_secrets), so this branch
        # is unreachable in a production deployment regardless of config.
        if settings.otp_dev_console_fallback_enabled and settings.app_env != "production":
            return ConsoleOtpProvider()
        raise OtpProviderNotConfiguredError("Payamak Panel is not configured")
    return PayamakPanelOtpProvider(
        PayamakPanelConfig(
            username=username,
            password=password,
            sender_number=sender_number,
            timeout_seconds=settings.payamak_panel_timeout_seconds,
        )
    )
