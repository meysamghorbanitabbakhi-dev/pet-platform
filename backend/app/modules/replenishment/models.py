from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReplenishmentReservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A system-proposed reorder for one inventory unit's depletion cycle
    (Workstream 3) -- at most one per unit, ever (`inventory_unit_id` is
    unique): a unit has exactly one "need window" from opened to exhausted,
    so a resolved reservation (approved/declined/expired/invalidated) is
    never superseded by a second one for the same unit.

    Created by the scheduler when a unit's pessimistic depletion estimate
    (FoodEstimate.low_days) crosses settings.replenishment_reservation_lead_days
    and a reorderable offer exists for its product -- never fabricated
    without both facts. Approval creates a real, full-payment Order via the
    existing CheckoutService (no reconfirmed-price concept here, unlike
    Workstream 2C's reserve-now: the customer approves at whatever the
    live offer price is when they act, exactly like a manual reorder
    would) -- there is no deposit and no auto-charge either way.
    """

    __tablename__ = "replenishment_reservations"
    __table_args__ = (
        UniqueConstraint("inventory_unit_id", name="one_reservation_per_unit"),
        UniqueConstraint("idempotency_key", name="one_reservation_per_idempotency_key"),
        CheckConstraint(
            "status IN ('pending_approval','approved','declined','expired','invalidated')",
            name="valid_status",
        ),
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint(
            "predicted_depletion_low_days >= 0 AND "
            "predicted_depletion_high_days >= predicted_depletion_low_days",
            name="valid_depletion_range",
        ),
    )

    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("households_households.id"), index=True, nullable=False
    )
    # Nullable: FoodEstimate.scope can be 'household' (shared consumption,
    # no single pet attributable) -- the reservation mirrors that.
    pet_id: Mapped[UUID | None] = mapped_column(ForeignKey("pets_pets.id"))
    inventory_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_units.id"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(ForeignKey("catalog_products.id"), nullable=False)
    offer_id: Mapped[UUID] = mapped_column(ForeignKey("catalog_offers.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # The specific FoodEstimate row (and its range, snapshotted) that
    # triggered this reservation -- "estimate version" per the brief.
    # Refreshed in place (not superseded by a new reservation row) if a
    # later, still-active estimate materially worsens while this stays
    # pending_approval.
    source_food_estimate_id: Mapped[UUID] = mapped_column(
        ForeignKey("food_estimation_estimates.id"), nullable=False
    )
    predicted_depletion_low_days: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_depletion_high_days: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending_approval", nullable=False)
    approval_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set once, only for the final expiry reminder -- never resent, and
    # never used for the initial creation notification (that one is
    # tracked durably by its own outbox event, same as every other
    # propose-style notification in this codebase).
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resulting_order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders_orders.id"))


class ReplenishmentReservationEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only status history, mirroring the purchasing-batch,
    order-fulfillment, and reservation event patterns."""

    __tablename__ = "replenishment_reservation_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created','refreshed','approved','declined','expired',"
            "'invalidated')",
            name="valid_event_type",
        ),
    )

    reservation_id: Mapped[UUID] = mapped_column(
        ForeignKey("replenishment_reservations.id"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    identity_id: Mapped[UUID | None] = mapped_column(ForeignKey("identity_auth_identities.id"))
