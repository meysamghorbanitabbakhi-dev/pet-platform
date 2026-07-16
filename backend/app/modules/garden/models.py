from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GardenReward(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "garden_rewards"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="source_once"),
        CheckConstraint("state IN ('revealed','placed','stored')", name="valid_state"),
        CheckConstraint(
            "source_type IN ('journey_completion','owner_milestone',"
            "'profile_enrichment','durable_memory')",
            name="eligible_source",
        ),
    )

    pet_id: Mapped[UUID] = mapped_column(ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True)
    diary_entry_id: Mapped[UUID] = mapped_column(ForeignKey("diary_entries.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    object_key: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="revealed", nullable=False)
    quadrant: Mapped[int | None] = mapped_column(Integer)
    position_x: Mapped[int | None] = mapped_column(Integer)
    position_y: Mapped[int | None] = mapped_column(Integer)
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
