from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class PaymentRequest:
    amount_irr: int
    callback_url: str
    description: str
    order_id: str
    mobile_e164: str | None = None


@dataclass(frozen=True, slots=True)
class PaymentInitiation:
    provider_reference: str
    redirect_url: str


@dataclass(frozen=True, slots=True)
class PaymentVerification:
    state: Literal["verified", "already_verified"]
    provider_reference: str
    provider_transaction_id: str
    masked_card: str | None
    card_hash: str | None
    fee_irr: int


@dataclass(frozen=True, slots=True)
class PaymentInquiry:
    state: Literal["verified", "paid_unverified", "in_bank", "failed", "reversed"]
    provider_reference: str


@dataclass(frozen=True, slots=True)
class PaymentReversal:
    reversed: bool
    provider_reference: str


class PaymentGateway(Protocol):
    async def initiate(self, request: PaymentRequest) -> PaymentInitiation: ...

    async def verify(self, *, provider_reference: str, amount_irr: int) -> PaymentVerification: ...

    async def inquiry(self, *, provider_reference: str) -> PaymentInquiry: ...

    async def reverse(self, *, provider_reference: str) -> PaymentReversal: ...
