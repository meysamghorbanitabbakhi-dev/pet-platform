from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CustomerRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "support_customer_requests"
    __table_args__ = (
        CheckConstraint(
            "request_type IN ('support','concierge_sourcing')",
            name="valid_request_type",
        ),
        CheckConstraint(
            "contact_preference IN ('in_app','sms')",
            name="valid_contact_preference",
        ),
        CheckConstraint(
            "status IN ('submitted','in_review','resolved','closed')",
            name="valid_status",
        ),
        UniqueConstraint("identity_id", "idempotency_key", name="identity_request_key"),
    )

    identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("households_households.id"), index=True, nullable=False
    )
    request_type: Mapped[str] = mapped_column(String(30), nullable=False)
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders_orders.id"), index=True)
    offer_id: Mapped[UUID | None] = mapped_column(ForeignKey("catalog_offers.id"), index=True)
    product_query_fa: Mapped[str | None] = mapped_column(String(500))
    message_fa: Mapped[str] = mapped_column(Text, nullable=False)
    contact_preference: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="submitted", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str | None] = mapped_column(String(64))


class CustomerRequestStatusAudit(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "support_customer_request_status_audit"

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("support_customer_requests.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    operator_identity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
    old_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
