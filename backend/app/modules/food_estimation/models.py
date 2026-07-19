from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FoodEstimate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "food_estimation_estimates"
    __table_args__ = (
        CheckConstraint(
            "(low_days IS NULL AND high_days IS NULL) OR (low_days >= 0 AND high_days >= low_days)",
            name="valid_range",
        ),
        CheckConstraint("confidence IN ('low','medium','high')", name="valid_confidence"),
        CheckConstraint("status IN ('active','corrected','exhausted')", name="valid_status"),
    )

    inventory_unit_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_units.id"), index=True)
    low_days: Mapped[int | None] = mapped_column(Integer)
    high_days: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    basis: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), default="household", nullable=False)
    pet_id: Mapped[UUID | None] = mapped_column(ForeignKey("pets_pets.id"))
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[dict[str, object] | None] = mapped_column(JSONB)
