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
    # Which version of InventoryService's low_days/high_days formula
    # produced this row (app.modules.inventory.service._ALGORITHM_VERSION)
    # -- lets a future formula change be distinguished from old rows when
    # auditing predictions against real outcomes, rather than every
    # historical estimate silently looking like it came from whatever
    # formula is live today. NULL only for rows written before this
    # column existed (see migration 20260720_0039's backfill, which uses
    # the explicit sentinel 'legacy_unversioned' rather than guessing).
    algorithm_version: Mapped[str | None] = mapped_column(String(20))
    # canonical_request_hash(...) over every material input to the
    # calculation (including algorithm_version) -- open_and_estimate's
    # replay-safety check compares this instead of a hand-picked subset
    # of fields, so a change to any material input (not just the ones
    # someone remembered to compare) correctly fails replay instead of
    # silently returning stale results. NULL for legacy rows: their
    # original daily_portion_grams was never captured in `provenance`,
    # so reconstructing a hash for them would be a guess, not a fact.
    request_hash: Mapped[str | None] = mapped_column(String(64))
