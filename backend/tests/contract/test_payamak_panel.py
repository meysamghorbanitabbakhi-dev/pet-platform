from urllib.parse import parse_qs

import httpx
import pytest
from app.integrations.otp.payamak_panel import (
    PayamakPanelConfig,
    PayamakPanelError,
    PayamakPanelOtpProvider,
)


def _provider(handler: httpx.MockTransport) -> PayamakPanelOtpProvider:
    return PayamakPanelOtpProvider(
        PayamakPanelConfig(
            username="test-user",
            password="test-password",
            sender_number="test-sender",
        ),
        client=httpx.AsyncClient(transport=handler),
    )


@pytest.mark.asyncio
async def test_sends_generated_code_as_form_data() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = parse_qs(request.content.decode())
        assert str(request.url) == "https://rest.payamak-panel.com/api/SendSMS/SendSMS"
        assert payload["username"] == ["test-user"]
        assert payload["password"] == ["test-password"]
        assert payload["to"] == ["09121234567"]
        assert payload["from"] == ["test-sender"]
        assert "483920" in payload["text"][0]
        assert payload["isFlash"] == ["false"]
        return httpx.Response(200, json={"RetStatus": 1, "Value": "message-123"})

    reference = await _provider(httpx.MockTransport(handler)).send_code(
        mobile_e164="+989121234567",
        code="483920",
        correlation_id="challenge-123",
    )

    assert reference == "message-123"


@pytest.mark.asyncio
async def test_rejected_delivery_raises_canonical_error() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"RetStatus": 0, "Value": "rejected"})

    with pytest.raises(PayamakPanelError) as caught:
        await _provider(httpx.MockTransport(handler)).send_code(
            mobile_e164="+989121234567",
            code="483920",
            correlation_id="challenge-123",
        )

    assert caught.value.status == 0
