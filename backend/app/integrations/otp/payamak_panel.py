from __future__ import annotations

from dataclasses import dataclass

import httpx


class PayamakPanelError(Exception):
    def __init__(self, *, status: int | None, message: str) -> None:
        super().__init__(f"Payamak Panel delivery failed: status={status} message={message}")
        self.status = status
        self.provider_message = message


@dataclass(frozen=True, slots=True)
class PayamakPanelConfig:
    username: str
    password: str
    sender_number: str
    timeout_seconds: float = 15
    endpoint: str = "https://rest.payamak-panel.com/api/SendSMS/SendSMS"
    message_template: str = "کد تأیید شما: {code}\nاین کد را در اختیار دیگران قرار ندهید."


class PayamakPanelOtpProvider:
    def __init__(self, config: PayamakPanelConfig, client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._client = client or httpx.AsyncClient(timeout=config.timeout_seconds)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def send_code(self, *, mobile_e164: str, code: str, correlation_id: str) -> str:
        return await self.send_message(
            mobile_e164=mobile_e164,
            text=self._config.message_template.format(code=code),
            correlation_id=correlation_id,
        )

    async def send_message(self, *, mobile_e164: str, text: str, correlation_id: str) -> str:
        del correlation_id
        payload = {
            "username": self._config.username,
            "password": self._config.password,
            "to": _to_local_mobile(mobile_e164),
            "from": self._config.sender_number,
            "text": text,
            "isFlash": "false",
        }
        try:
            response = await self._client.post(self._config.endpoint, data=payload)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PayamakPanelError(status=None, message=str(exc)) from exc
        if not isinstance(body, dict):
            raise PayamakPanelError(status=None, message="non-object JSON response")
        status = _integer(body.get("RetStatus"))
        provider_value = str(body.get("Value", ""))
        if status != 1:
            raise PayamakPanelError(
                status=status, message=provider_value or "provider rejected delivery"
            )
        return provider_value


def _to_local_mobile(mobile_e164: str) -> str:
    if not mobile_e164.startswith("+989") or len(mobile_e164) != 13:
        raise ValueError("mobile_e164 must be a normalized Iranian mobile number")
    return "0" + mobile_e164[3:]


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
