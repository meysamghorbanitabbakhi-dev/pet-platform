from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.time import utc_now
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.orders.models import Order


class FulfillmentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders_fulfillment_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('sourcing_started','sourcing_failed','in_transit',"
            "'delayed','delivered','cancelled','resolution_recorded')",
            name="valid_event_type",
        ),
    )

    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders_orders.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    operator_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), nullable=False
    )


class FulfillmentTransitionError(Exception):
    pass


_TRANSITIONS: dict[str, dict[str, str]] = {
    "paid": {"sourcing_started": "sourcing", "cancelled": "cancelled"},
    "sourcing": {
        "sourcing_failed": "failed",
        "in_transit": "in_transit",
        "cancelled": "cancelled",
    },
    "in_transit": {"delayed": "in_transit", "delivered": "delivered"},
}


def apply_fulfillment_transition(
    order: Order,
    *,
    event_type: str,
    operator_identity_id: UUID,
    reason: str | None,
) -> FulfillmentEvent:
    target = _TRANSITIONS.get(order.status, {}).get(event_type)
    if target is None:
        raise FulfillmentTransitionError(
            f"event {event_type} is not allowed while order is {order.status}"
        )
    now = utc_now()
    order.status = target
    if event_type == "delivered":
        order.delivered_at = now
    return FulfillmentEvent(
        order_id=order.id,
        event_type=event_type,
        occurred_at=now,
        reason=reason,
        operator_identity_id=operator_identity_id,
    )
