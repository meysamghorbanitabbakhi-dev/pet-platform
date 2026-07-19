from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Reservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A zero-charge hold on a 'reserve'-mode offer.

    Lifecycle: requested -> proposed (operator reconfirmed price/
    availability) -> converted (customer approved; a real, full-payment
    Order now exists) | customer_declined | operator_declined | expired.
    No money ever moves until the resulting Order goes through the
    existing PaymentService flow -- there is no deposit concept.
    """

    __tablename__ = "reservations_reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('requested','proposed','converted','customer_declined',"
            "'operator_declined','expired')",
            name="valid_status",
        ),
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("requested_price_irr > 0", name="positive_requested_price"),
        CheckConstraint(
            "reconfirmed_price_irr IS NULL OR reconfirmed_price_irr > 0",
            name="positive_reconfirmed_price",
        ),
    )

    customer_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("households_households.id"), nullable=False
    )
    offer_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_offers.id"), index=True, nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Snapshot of offer.price_irr at request time -- what the customer saw.
    # Never charged directly; see reconfirmed_price_irr.
    requested_price_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    operator_review_by: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="requested", nullable=False)

    # Source/price reconfirmation + proposal to the customer (operator
    # action). reconfirmed_price_irr is what the resulting order actually
    # charges on conversion -- never the live offer.price_irr at whatever
    # moment the customer happens to click approve, which could have moved
    # again since reconfirmation.
    reconfirmed_price_irr: Mapped[int | None] = mapped_column(Integer)
    reconfirmed_available: Mapped[bool | None] = mapped_column(Boolean)
    proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposed_by_operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    proposal_reason: Mapped[str | None] = mapped_column(Text)
    customer_respond_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decline_reason: Mapped[str | None] = mapped_column(Text)

    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders_orders.id"))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReservationEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only status history for a reservation, mirroring the
    purchasing-batch and order-fulfillment event patterns."""

    __tablename__ = "reservations_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('requested','proposed','approved','customer_declined',"
            "'operator_declined','expired','converted')",
            name="valid_event_type",
        ),
    )

    reservation_id: Mapped[UUID] = mapped_column(
        ForeignKey("reservations_reservations.id"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    operator_identity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    customer_identity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
