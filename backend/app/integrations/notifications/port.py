from typing import Protocol


class SmsProvider(Protocol):
    async def send_message(self, *, mobile_e164: str, text: str, correlation_id: str) -> str: ...

    async def aclose(self) -> None: ...
