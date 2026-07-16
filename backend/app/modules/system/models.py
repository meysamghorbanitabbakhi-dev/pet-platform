from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class OutboxEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "system_outbox_events"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
        Index("ix_outbox_dispatchable", "published_at", "available_at", "claimed_until"),
    )

    event_id: Mapped[UUID] = mapped_column(unique=True, default=uuid4, nullable=False)
    event_type: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WebhookInboxEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "system_webhook_inbox"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id"),
        CheckConstraint(
            "processing_status IN ('received','processed','rejected','failed')",
            name="valid_processing_status",
        ),
    )

    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(200))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    headers: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(30), default="received", nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class IdempotencyRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "system_idempotency_records"
    __table_args__ = (
        UniqueConstraint("scope", "idempotency_key"),
        CheckConstraint(
            "state IN ('processing','completed','failed')", name="valid_idempotency_state"
        ),
    )

    scope: Mapped[str] = mapped_column(String(150), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="processing", nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    locked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OperatorAuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "system_operator_audit_log"
    __table_args__ = (Index("ix_operator_audit_resource", "resource_type", "resource_id"),)

    operator_identity_id: Mapped[UUID | None]
    action: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    before_facts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_facts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_ip: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True, nullable=False)
