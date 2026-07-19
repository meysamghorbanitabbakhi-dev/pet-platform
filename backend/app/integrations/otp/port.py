from typing import Protocol


class OtpProvider(Protocol):
    #: Whether this provider can report a post-submission delivery outcome
    #: (DLR/webhook/poll) beyond synchronous submission accepted/rejected.
    #: False for every provider integrated today. A future provider that
    #: sets this True still reports through the same OtpChallenge row via
    #: OtpService -- this flag does not change challenge ownership.
    supports_delivery_receipts: bool

    async def send_code(self, *, mobile_e164: str, code: str, correlation_id: str) -> str:
        """Send an OTP and return the provider reference."""
        ...

    async def aclose(self) -> None: ...
