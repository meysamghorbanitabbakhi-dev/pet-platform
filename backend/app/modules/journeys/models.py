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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class JourneyDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "journeys_definitions"
    __table_args__ = (
        UniqueConstraint("key", "version", name="key_version"),
        CheckConstraint(
            "approval_status IN ('draft','approved','retired')", name="valid_approval_status"
        ),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title_fa: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(200))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PetJourney(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "journeys_pet_journeys"
    __table_args__ = (
        CheckConstraint("status IN ('active','paused','stopped','completed')", name="valid_status"),
    )

    pet_id: Mapped[UUID] = mapped_column(ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True)
    definition_id: Mapped[UUID] = mapped_column(ForeignKey("journeys_definitions.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_reason: Mapped[str | None] = mapped_column(Text)
    definition_version: Mapped[int | None] = mapped_column(Integer)
    definition_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    completion_effects_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JourneyCheckIn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "journey_check_ins"
    __table_args__ = (
        UniqueConstraint("journey_id", "check_in_key", name="journey_check_in_once"),
        UniqueConstraint("journey_id", "idempotency_key", name="journey_check_in_key_once"),
    )

    journey_id: Mapped[UUID] = mapped_column(
        ForeignKey("journeys_pet_journeys.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    check_in_key: Mapped[str] = mapped_column(String(100), nullable=False)
    answer_key: Mapped[str] = mapped_column(String(100), nullable=False)
    submitted_by_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True, nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
