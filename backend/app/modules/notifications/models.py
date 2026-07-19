from __future__ import annotations

from datetime import datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications_preferences"
    __table_args__ = (
        UniqueConstraint("identity_id", "channel", "event_key", name="identity_channel_event"),
    )

    identity_id: Mapped[UUID] = mapped_column(ForeignKey("identity_auth_identities.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    event_key: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quiet_start_local: Mapped[time | None] = mapped_column(Time)
    quiet_end_local: Mapped[time | None] = mapped_column(Time)


class NotificationTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications_templates"
    __table_args__ = (
        UniqueConstraint("event_key", "channel", "version", name="event_channel_version"),
    )

    event_key: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body_fa: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications_notifications"
    __table_args__ = (
        UniqueConstraint(
            "event_key",
            "source_id",
            "recipient_identity_id",
            "channel",
            name="event_source_recipient_channel",
        ),
        CheckConstraint(
            "status IN ('queued','deferred','sent','failed','suppressed')", name="valid_status"
        ),
        CheckConstraint(
            "destination_kind IN "
            "('order','inventory_unit','journey','customer_request','offer','none')",
            name="valid_notification_destination_kind",
        ),
    )

    recipient_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
    event_key: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    destination_kind: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    destination_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class NotificationAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications_attempts"
    __table_args__ = (CheckConstraint("status IN ('sent','failed')", name="valid_status"),)

    notification_id: Mapped[UUID] = mapped_column(
        ForeignKey("notifications_notifications.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255))
    error_code: Mapped[str | None] = mapped_column(String(100))
