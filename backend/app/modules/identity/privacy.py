from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PrivacyRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "identity_privacy_requests"
    __table_args__ = (
        CheckConstraint(
            "request_type IN ('export','disable','anonymize')", name="valid_request_type"
        ),
        CheckConstraint(
            "status IN ('requested','awaiting_policy','completed','rejected')",
            name="valid_status",
        ),
    )

    identity_id: Mapped[UUID] = mapped_column(ForeignKey("identity_auth_identities.id"), index=True)
    request_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    result_facts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
