import json

import httpx
import pytest
from app.integrations.payment.port import PaymentRequest
from app.integrations.payment.zarinpal import (
    ZarinpalConfig,
    ZarinpalError,
    ZarinpalGateway,
    callback_allows_verification,
)

AUTHORITY = "S00000000000000000000000000000000001"


def _gateway(handler: httpx.MockTransport) -> ZarinpalGateway:
    client = httpx.AsyncClient(transport=handler)
    return ZarinpalGateway(
        ZarinpalConfig(merchant_id="00000000-0000-0000-0000-000000000000", sandbox=True),
        client=client,
    )


@pytest.mark.asyncio
async def test_request_uses_irr_and_sandbox_redirect() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert str(request.url).endswith("/request.json")
        assert request.url.host == "sandbox.zarinpal.com"
        assert payload["currency"] == "IRR"
        assert payload["amount"] == 12_000_000
        assert payload["metadata"]["mobile"] == "09121234567"
        return httpx.Response(
            200,
            json={
                "data": {"code": 100, "message": "Success", "authority": AUTHORITY},
                "errors": [],
            },
        )

    gateway = _gateway(httpx.MockTransport(handler))
    result = await gateway.initiate(
        PaymentRequest(
            amount_irr=12_000_000,
            callback_url="https://example.test/payments/callback",
            description="Order 123",
            order_id="123",
            mobile_e164="+989121234567",
        )
    )

    assert result.provider_reference == AUTHORITY
    assert result.redirect_url == f"https://sandbox.zarinpal.com/pg/StartPay/{AUTHORITY}"


@pytest.mark.asyncio
@pytest.mark.parametrize(("code", "state"), [(100, "verified"), (101, "already_verified")])
async def test_verify_treats_100_and_101_as_success(code: int, state: str) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "code": code,
                    "message": "Verified",
                    "ref_id": 98765,
                    "card_pan": "502229******5995",
                    "card_hash": "HASH",
                    "fee": 0,
                },
                "errors": [],
            },
        )

    result = await _gateway(httpx.MockTransport(handler)).verify(
        provider_reference=AUTHORITY, amount_irr=1_000_000
    )

    assert result.state == state
    assert result.provider_transaction_id == "98765"


@pytest.mark.asyncio
async def test_provider_errors_are_canonical() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": {}, "errors": {"code": -50, "message": "amount mismatch"}},
        )

    with pytest.raises(ZarinpalError) as caught:
        await _gateway(httpx.MockTransport(handler)).verify(
            provider_reference=AUTHORITY, amount_irr=1_000_000
        )

    assert caught.value.operation == "verify"
    assert caught.value.code == -50


def test_only_ok_callback_may_trigger_verification() -> None:
    assert callback_allows_verification("OK") is True
    assert callback_allows_verification("NOK") is False
    assert callback_allows_verification(None) is False
