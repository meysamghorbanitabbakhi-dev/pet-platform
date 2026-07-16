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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PaymentAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments_attempts"
    __table_args__ = (
        CheckConstraint("amount_irr > 0", name="positive_amount"),
        CheckConstraint("currency = 'IRR'", name="irr_only"),
        CheckConstraint(
            "status IN ('created','redirect_ready','verified','failed')", name="valid_status"
        ),
        UniqueConstraint("order_id", "idempotency_key", name="order_payment_key"),
        UniqueConstraint("provider", "provider_reference", name="provider_reference"),
    )

    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders_orders.id"), index=True)
    provider: Mapped[str] = mapped_column(String(30), default="zarinpal", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="created", nullable=False)
    amount_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IRR", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255))
    provider_transaction_id: Mapped[str | None] = mapped_column(String(255))
    redirect_url: Mapped[str | None] = mapped_column(Text)
    masked_card: Mapped[str | None] = mapped_column(String(64))
    card_hash: Mapped[str | None] = mapped_column(String(255))
    fee_irr: Mapped[int | None] = mapped_column(Integer)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
