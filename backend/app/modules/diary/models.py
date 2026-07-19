from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DiaryEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "diary_entries"
    __table_args__ = (UniqueConstraint("source_type", "source_id", name="source_once"),)

    pet_id: Mapped[UUID] = mapped_column(ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True)
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title_fa: Mapped[str] = mapped_column(String(300), nullable=False)
    note_fa: Mapped[str | None] = mapped_column(Text)
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
