from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.orders.fulfillment import (
    FulfillmentTransitionError,
    apply_fulfillment_transition,
)
from app.modules.orders.models import Order
from app.modules.wallet.service import _add_months


def _order(status: str) -> Order:
    return Order(
        id=uuid4(),
        customer_identity_id=uuid4(),
        household_id=uuid4(),
        status=status,
        currency="IRR",
        merchandise_total_irr=1_000_000,
        checkout_idempotency_key="checkout-key",
    )


def test_fulfillment_follows_explicit_state_machine() -> None:
    order = _order("paid")
    event = apply_fulfillment_transition(
        order,
        event_type="sourcing_started",
        operator_identity_id=uuid4(),
        reason="Supplier contact started",
    )
    assert order.status == "sourcing"
    assert event.event_type == "sourcing_started"


def test_delivery_cannot_skip_sourcing_and_transit() -> None:
    with pytest.raises(FulfillmentTransitionError):
        apply_fulfillment_transition(
            _order("paid"),
            event_type="delivered",
            operator_identity_id=uuid4(),
            reason="Invalid shortcut",
        )


def test_wallet_expiry_uses_calendar_months() -> None:
    value = datetime(2026, 11, 30, tzinfo=UTC)
    assert _add_months(value, 3) == datetime(2027, 2, 28, tzinfo=UTC)
