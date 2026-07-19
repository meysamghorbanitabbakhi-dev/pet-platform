from __future__ import annotations

import logging

logger = logging.getLogger("otp.dev_console")


class ConsoleOtpProvider:
    """Local/CI-only stand-in for a real SMS provider: logs outbound messages
    instead of sending them. Only ever constructed by build_otp_provider when
    otp_dev_console_fallback_enabled is set, which itself can never be true in
    production (see Settings.validate_production_secrets).

    Satisfies both OtpProvider and notifications.SmsProvider structurally,
    since build_otp_provider's result is reused by the pending-SMS worker
    (app.workers.scheduler._run_pending_sms_job) for general transactional
    SMS, not just OTP codes."""

    supports_delivery_receipts = False

    async def aclose(self) -> None:
        return None

    async def send_code(self, *, mobile_e164: str, code: str, correlation_id: str) -> str:
        logger.warning(
            "OTP dev console fallback: mobile=%s code=%s correlation_id=%s "
            "(no SMS provider configured; this only happens outside production)",
            mobile_e164,
            code,
            correlation_id,
        )
        return f"dev-console:{correlation_id}"

    async def send_message(self, *, mobile_e164: str, text: str, correlation_id: str) -> str:
        logger.warning(
            "SMS dev console fallback: mobile=%s correlation_id=%s text=%r "
            "(no SMS provider configured; this only happens outside production)",
            mobile_e164,
            correlation_id,
            text,
        )
        return f"dev-console:{correlation_id}"
