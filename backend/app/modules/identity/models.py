from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class AuthIdentity(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "identity_auth_identities"
    __table_args__ = (
        CheckConstraint("identity_type IN ('customer','operator')", name="valid_identity_type"),
        CheckConstraint("status IN ('active','disabled')", name="valid_status"),
    )

    identity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    mobile_e164: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OtpChallenge(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "identity_otp_challenges"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
        CheckConstraint("max_attempts > 0", name="max_attempts_positive"),
        CheckConstraint(
            "delivery_status IN ('pending','sent','failed')", name="valid_delivery_status"
        ),
    )

    mobile_e164: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255))
    delivery_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    delivery_error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuthSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "identity_auth_sessions"

    identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    access_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)
    source_ip: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
