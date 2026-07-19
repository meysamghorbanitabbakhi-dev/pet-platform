from typing import Protocol


class OtpProvider(Protocol):
    async def send_code(self, *, mobile_e164: str, code: str, correlation_id: str) -> str:
        """Send an OTP and return the provider reference."""
        ...

    async def aclose(self) -> None: ...
