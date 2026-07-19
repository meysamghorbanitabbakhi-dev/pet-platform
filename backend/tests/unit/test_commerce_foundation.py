from uuid import uuid4

import pytest
from app.modules.checkout.service import CheckoutItem
from app.modules.identity.sessions import SessionService
from app.modules.payments.service import PaymentService


def test_checkout_item_keeps_quantity_and_offer_identity() -> None:
    offer_id = uuid4()
    item = CheckoutItem(offer_id=offer_id, quantity=2)
    assert item.offer_id == offer_id
    assert item.quantity == 2


def test_payment_commitment_uses_bounded_policy_value() -> None:
    PaymentService(delivery_commitment_hours=366)
    PaymentService(delivery_commitment_hours=336)
    with pytest.raises(ValueError, match="between"):
        PaymentService(delivery_commitment_hours=0)


def test_session_tokens_require_a_strong_pepper() -> None:
    with pytest.raises(ValueError, match="32"):
        SessionService(pepper="weak")
