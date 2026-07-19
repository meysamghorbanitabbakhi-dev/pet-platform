from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.orders.models import Order, OrderLine
from app.modules.purchasing.service import (
    PurchasingError,
    is_order_cancellation_eligible,
    void_allocations_for_cancelled_order,
)

# The same source-status set apply_fulfillment_transition allows into
# 'cancelled' for operator-driven cancellation -- mirrored here, not
# imported, because the two paths have different actors, different
# eligibility gates and different side effects (no FulfillmentEvent,
# refund bookkeeping instead). Keep both in sync if this set ever changes.
_CUSTOMER_CANCELLABLE_STATUSES = ("paid", "sourcing")


class OrderCancellation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A customer-initiated cancellation of a paid order before supplier
    financial commitment (Workstream 2B). At most one per order --
    cancelling is a one-time, terminal transition, not a repeatable event.

    Refunds are operator-attested, never an automatic payment-gateway
    reversal (explicit product decision covering both this and a
    declined/expired shelf-life exception, Workstream 2E): refund_status
    starts 'owed' and only becomes 'operator_attested' once an operator
    records evidence that the money was actually paid back.
    """

    __tablename__ = "orders_cancellations"
    __table_args__ = (
        UniqueConstraint("order_id", name="one_cancellation_per_order"),
        CheckConstraint(
            "refund_status IN ('owed','operator_attested')", name="valid_refund_status"
        ),
        CheckConstraint("refund_amount_irr > 0", name="positive_refund_amount"),
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders_orders.id"), nullable=False, index=True
    )
    cancelled_by_customer_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # Immutable snapshot of the order and its lines at the moment of
    # cancellation -- the Order row keeps changing (status, etc.), so this
    # is the durable record of exactly what was paid for and owed back.
    order_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    refund_amount_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    refund_status: Mapped[str] = mapped_column(String(20), default="owed", nullable=False)
    refund_attested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refund_attested_by_operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    refund_evidence_file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("trust_evidence_files.id")
    )
    refund_reference: Mapped[str | None] = mapped_column(String(300))


class CancellationError(Exception):
    pass


def _order_snapshot(order: Order, lines: list[OrderLine]) -> dict[str, Any]:
    return {
        "order": {
            "id": str(order.id),
            "status": order.status,
            "currency": order.currency,
            "merchandise_total_irr": order.merchandise_total_irr,
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
            "delivery_commitment_at": (
                order.delivery_commitment_at.isoformat()
                if order.delivery_commitment_at
                else None
            ),
        },
        "lines": [
            {
                "id": str(line.id),
                "offer_id": str(line.offer_id),
                "sku": line.sku_snapshot,
                "quantity": line.quantity,
                "unit_price_irr": line.unit_price_irr,
                "line_total_irr": line.line_total_irr,
            }
            for line in lines
        ],
    }


async def cancel_order_by_customer(
    session: AsyncSession,
    *,
    order: Order,
    customer_identity_id: UUID,
    reason: str,
) -> OrderCancellation:
    """Cancel a paid order before supplier financial commitment.

    Idempotent/replay-safe: cancelling an already-cancelled order returns
    the existing record unchanged. Caller must have already row-locked
    `order` (with_for_update) so this and a concurrent cancel of the same
    order serialize correctly.
    """
    existing = await session.scalar(
        select(OrderCancellation).where(OrderCancellation.order_id == order.id)
    )
    if existing is not None:
        return existing
    if order.status not in _CUSTOMER_CANCELLABLE_STATUSES:
        raise CancellationError("order_not_cancellable_in_current_status")
    try:
        await void_allocations_for_cancelled_order(session, order_id=order.id)
    except PurchasingError as exc:
        raise CancellationError("order_already_committed_for_sourcing") from exc

    lines = list(
        (await session.scalars(select(OrderLine).where(OrderLine.order_id == order.id))).all()
    )
    order.status = "cancelled"
    cancellation = OrderCancellation(
        order_id=order.id,
        cancelled_by_customer_identity_id=customer_identity_id,
        reason=reason,
        order_snapshot=_order_snapshot(order, lines),
        refund_amount_irr=order.merchandise_total_irr,
        refund_status="owed",
    )
    session.add(cancellation)
    await session.flush()
    return cancellation


async def is_order_cancellation_eligible_now(session: AsyncSession, *, order: Order) -> bool:
    """Read-only eligibility check for display purposes (e.g. whether to
    show a Cancel button). Not used to gate the actual cancellation write
    -- see cancel_order_by_customer / void_allocations_for_cancelled_order
    for the locked, race-safe version."""
    if order.status not in _CUSTOMER_CANCELLABLE_STATUSES:
        return False
    already_cancelled = await session.scalar(
        select(OrderCancellation.id).where(OrderCancellation.order_id == order.id)
    )
    if already_cancelled is not None:
        return False
    return await is_order_cancellation_eligible(session, order_id=order.id)
