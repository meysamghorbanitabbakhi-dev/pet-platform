from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.integrations.payment.port import (
    PaymentInitiation,
    PaymentInquiry,
    PaymentRequest,
    PaymentReversal,
    PaymentVerification,
)


class ZarinpalError(Exception):
    def __init__(self, *, operation: str, code: int | None, message: str) -> None:
        super().__init__(f"Zarinpal {operation} failed: code={code} message={message}")
        self.operation = operation
        self.code = code
        self.provider_message = message


@dataclass(frozen=True, slots=True)
class ZarinpalConfig:
    merchant_id: str
    sandbox: bool = True
    timeout_seconds: float = 15

    @property
    def api_base_url(self) -> str:
        if self.sandbox:
            return "https://sandbox.zarinpal.com/pg/v4/payment"
        return "https://payment.zarinpal.com/pg/v4/payment"

    @property
    def start_pay_base_url(self) -> str:
        if self.sandbox:
            return "https://sandbox.zarinpal.com/pg/StartPay"
        return "https://payment.zarinpal.com/pg/StartPay"


class ZarinpalGateway:
    def __init__(self, config: ZarinpalConfig, client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._client = client or httpx.AsyncClient(timeout=config.timeout_seconds)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def initiate(self, request: PaymentRequest) -> PaymentInitiation:
        if request.amount_irr <= 0:
            raise ValueError("amount_irr must be positive")
        metadata: dict[str, str] = {"order_id": request.order_id}
        if request.mobile_e164 is not None:
            metadata["mobile"] = _to_iranian_local_mobile(request.mobile_e164)
        payload: dict[str, Any] = {
            "merchant_id": self._config.merchant_id,
            "amount": request.amount_irr,
            "currency": "IRR",
            "description": request.description,
            "callback_url": request.callback_url,
            "metadata": metadata,
        }
        data = await self._post("request", payload)
        if _integer(data.get("code")) != 100 or not data.get("authority"):
            raise ZarinpalError(
                operation="request",
                code=_integer(data.get("code")),
                message=str(data.get("message", "unexpected response")),
            )
        authority = str(data["authority"])
        return PaymentInitiation(
            provider_reference=authority,
            redirect_url=f"{self._config.start_pay_base_url}/{authority}",
        )

    async def verify(self, *, provider_reference: str, amount_irr: int) -> PaymentVerification:
        data = await self._post(
            "verify",
            {
                "merchant_id": self._config.merchant_id,
                "amount": amount_irr,
                "authority": provider_reference,
            },
        )
        code = _integer(data.get("code"))
        if code not in (100, 101):
            raise ZarinpalError(
                operation="verify",
                code=code,
                message=str(data.get("message", "verification failed")),
            )
        reference_id = data.get("ref_id")
        if reference_id is None:
            raise ZarinpalError(
                operation="verify", code=code, message="successful response omitted ref_id"
            )
        return PaymentVerification(
            state="verified" if code == 100 else "already_verified",
            provider_reference=provider_reference,
            provider_transaction_id=str(reference_id),
            masked_card=_optional_string(data.get("card_pan")),
            card_hash=_optional_string(data.get("card_hash")),
            fee_irr=_integer(data.get("fee")) or 0,
        )

    async def inquiry(self, *, provider_reference: str) -> PaymentInquiry:
        data = await self._post(
            "inquiry",
            {"merchant_id": self._config.merchant_id, "authority": provider_reference},
        )
        provider_state = str(data.get("status", ""))
        state_map: dict[
            str, Literal["verified", "paid_unverified", "in_bank", "failed", "reversed"]
        ] = {
            "VERIFIED": "verified",
            "PAID": "paid_unverified",
            "IN_BANK": "in_bank",
            "FAILED": "failed",
            "REVERSED": "reversed",
        }
        if provider_state not in state_map:
            raise ZarinpalError(
                operation="inquiry",
                code=_integer(data.get("code")),
                message=f"unknown transaction state: {provider_state or 'missing'}",
            )
        return PaymentInquiry(
            state=state_map[provider_state], provider_reference=provider_reference
        )

    async def reverse(self, *, provider_reference: str) -> PaymentReversal:
        data = await self._post(
            "reverse",
            {"merchant_id": self._config.merchant_id, "authority": provider_reference},
        )
        code = _integer(data.get("code"))
        if code != 100:
            raise ZarinpalError(
                operation="reverse",
                code=code,
                message=str(data.get("message", "reverse failed")),
            )
        return PaymentReversal(reversed=True, provider_reference=provider_reference)

    async def _post(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(
                f"{self._config.api_base_url}/{operation}.json",
                json=payload,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ZarinpalError(operation=operation, code=None, message=str(exc)) from exc
        if not isinstance(body, dict):
            raise ZarinpalError(operation=operation, code=None, message="non-object JSON response")
        data = body.get("data")
        if isinstance(data, dict) and data:
            return data
        error_code, error_message = _extract_error(body.get("errors"))
        raise ZarinpalError(
            operation=operation,
            code=error_code,
            message=error_message or "provider returned no data",
        )


def callback_allows_verification(status: str | None) -> bool:
    return status == "OK"


def _to_iranian_local_mobile(mobile_e164: str) -> str:
    if not mobile_e164.startswith("+989") or len(mobile_e164) != 13:
        raise ValueError("mobile_e164 must be a normalized Iranian mobile number")
    return "0" + mobile_e164[3:]


def _extract_error(errors: object) -> tuple[int | None, str | None]:
    if isinstance(errors, dict):
        return _integer(errors.get("code")), _optional_string(errors.get("message"))
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            return _integer(first.get("code")), _optional_string(first.get("message"))
    return None, None


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None
