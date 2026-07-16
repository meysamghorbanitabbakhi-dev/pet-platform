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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('awaiting_payment','paid','sourcing','in_transit',"
            "'delivered','cancelled','failed')",
            name="valid_status",
        ),
        CheckConstraint("merchandise_total_irr > 0", name="positive_total"),
        CheckConstraint("currency = 'IRR'", name="irr_only"),
        UniqueConstraint(
            "customer_identity_id", "checkout_idempotency_key", name="customer_checkout_key"
        ),
    )

    customer_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households_households.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="awaiting_payment", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IRR", nullable=False)
    merchandise_total_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    checkout_idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_commitment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_address_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OrderLine(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "orders_order_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("unit_price_irr > 0", name="positive_unit_price"),
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders_orders.id", ondelete="CASCADE"), index=True
    )
    offer_id: Mapped[UUID] = mapped_column(ForeignKey("catalog_offers.id"), index=True)
    sku_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    title_fa_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)
    unit_label_fa_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    supplier_country_snapshot: Mapped[str] = mapped_column(String(2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrderLinePetPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders_order_line_pet_plans"
    __table_args__ = (UniqueConstraint("order_line_id", "pet_id", name="order_line_pet"),)

    order_line_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders_order_lines.id", ondelete="CASCADE"), index=True
    )
    pet_id: Mapped[UUID] = mapped_column(
        ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True
    )


class OrderDelayAcknowledgement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders_delay_acknowledgements"
    __table_args__ = (
        UniqueConstraint(
            "identity_id",
            "order_id",
            "idempotency_key",
            name="identity_order_ack_key",
        ),
        UniqueConstraint(
            "identity_id",
            "order_id",
            "delay_event_version",
            name="identity_order_delay_version",
        ),
    )

    identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True, nullable=False
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders_orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    delay_event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
