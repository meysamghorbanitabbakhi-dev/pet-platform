from app.core.config import Settings
from app.integrations.payment.zarinpal import ZarinpalConfig, ZarinpalGateway


class PaymentProviderNotConfiguredError(Exception):
    pass


def build_payment_gateway(settings: Settings) -> ZarinpalGateway:
    if not settings.zarinpal_merchant_id:
        raise PaymentProviderNotConfiguredError("Zarinpal merchant ID is not configured")
    return ZarinpalGateway(
        ZarinpalConfig(
            merchant_id=settings.zarinpal_merchant_id,
            sandbox=settings.zarinpal_sandbox,
            timeout_seconds=settings.zarinpal_timeout_seconds,
        )
    )
