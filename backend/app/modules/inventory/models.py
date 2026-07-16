from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InventoryUnit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory_units"
    __table_args__ = (
        CheckConstraint("source IN ('platform_order','external_purchase')", name="valid_source"),
        CheckConstraint(
            "state IN ('unopened','opened','exhausted','discarded')", name="valid_state"
        ),
        CheckConstraint(
            "initial_quantity_grams IS NULL OR initial_quantity_grams > 0",
            name="positive_initial_quantity",
        ),
        CheckConstraint(
            "remaining_quantity_grams IS NULL OR remaining_quantity_grams >= 0",
            name="nonnegative_remaining_quantity",
        ),
    )

    household_id: Mapped[UUID] = mapped_column(ForeignKey("households_households.id"), index=True)
    order_line_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("orders_order_lines.id"), unique=True
    )
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("catalog_products.id"), index=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="unopened", nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    initial_quantity_grams: Mapped[int | None] = mapped_column(Integer)
    remaining_quantity_grams: Mapped[int | None] = mapped_column(Integer)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exact_expiry_date: Mapped[date | None] = mapped_column(Date)
    sourcing_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supplier_country_snapshot: Mapped[str | None] = mapped_column(String(2))
    authenticity_basis: Mapped[str | None] = mapped_column(String(50))
    remaining_input_mode: Mapped[str | None] = mapped_column(String(20))
    remaining_low_grams: Mapped[int | None] = mapped_column(Integer)
    remaining_high_grams: Mapped[int | None] = mapped_column(Integer)
    remaining_provenance: Mapped[dict[str, object] | None] = mapped_column(JSONB)


class ConsumptionAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory_consumption_assignments"
    __table_args__ = (
        UniqueConstraint("inventory_unit_id", "pet_id", name="unit_pet"),
        CheckConstraint(
            "share_basis_points IS NULL OR "
            "(share_basis_points > 0 AND share_basis_points <= 10000)",
            name="valid_share",
        ),
    )

    inventory_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_units.id", ondelete="CASCADE"), index=True
    )
    pet_id: Mapped[UUID] = mapped_column(ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True)
    share_basis_points: Mapped[int | None] = mapped_column(Integer)
    daily_portion_grams: Mapped[int | None] = mapped_column(Integer)


class ReorderSnooze(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory_reorder_snoozes"
    __table_args__ = (UniqueConstraint("inventory_unit_id", "identity_id", name="unit_identity"),)

    inventory_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_units.id", ondelete="CASCADE"), index=True
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households_households.id"), index=True)
    identity_id: Mapped[UUID] = mapped_column(ForeignKey("identity_auth_identities.id"), index=True)
    snoozed_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snoozed_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    baseline_low_days: Mapped[int | None] = mapped_column(Integer)
