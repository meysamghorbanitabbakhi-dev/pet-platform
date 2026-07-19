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


class PurchaseBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A grouped or individual purchasing cycle for one offer.

    grouping_mode='aggregated' batches pool order lines from many
    households; grouping_mode='individual' batches always hold exactly one
    order line (exceptional/high-value offers, Decision 0.10 -- never
    pooled). Committing a batch (committed_at + evidence) is the durable
    supplier financial-commitment fact the customer cancellation boundary
    (Workstream 2B) is gated on -- a bare status change is not enough, per
    ADR-003.
    """

    __tablename__ = "purchasing_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open','committed','cancelled')", name="valid_status"
        ),
        CheckConstraint(
            "grouping_mode IN ('aggregated','individual')", name="valid_grouping_mode"
        ),
        CheckConstraint(
            "minimum_viable_threshold_quantity > 0", name="positive_threshold_quantity"
        ),
        CheckConstraint("allocated_quantity >= 0", name="nonnegative_allocated_quantity"),
    )

    offer_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_offers.id"), index=True, nullable=False
    )
    grouping_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    minimum_viable_threshold_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    threshold_reached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    committed_by_operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    commitment_evidence_file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("trust_evidence_files.id")
    )
    commitment_reference: Mapped[str | None] = mapped_column(String(300))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )


class PurchaseBatchAllocation(UUIDPrimaryKeyMixin, Base):
    """Which purchase batch a given order line's sourcing belongs to.

    Every order line for a sourced-after-payment offer gets exactly one
    allocation -- created once, at payment-verified time, never reassigned
    (replay-safe: allocating an already-allocated line is a no-op).
    """

    __tablename__ = "purchasing_batch_allocations"
    __table_args__ = (
        UniqueConstraint("order_line_id", name="one_batch_per_order_line"),
        CheckConstraint("quantity > 0", name="positive_quantity"),
    )

    purchase_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchasing_batches.id"), index=True, nullable=False
    )
    order_line_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders_order_lines.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PurchaseBatchEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only status history for a purchase batch (audit + replay-safety)."""

    __tablename__ = "purchasing_batch_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('opened','threshold_reached','committed','cancelled')",
            name="valid_event_type",
        ),
    )

    purchase_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchasing_batches.id"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    operator_identity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
