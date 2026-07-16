from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OrderResolution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders_resolutions"
    __table_args__ = (
        CheckConstraint(
            "resolution_type IN ('refund','replacement','substitution')",
            name="valid_resolution_type",
        ),
        CheckConstraint(
            "state IN ('awaiting_policy','approved','rejected','executed')",
            name="valid_state",
        ),
    )

    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders_orders.id"), index=True)
    resolution_type: Mapped[str] = mapped_column(String(30), nullable=False)
    state: Mapped[str] = mapped_column(String(30), default="awaiting_policy", nullable=False)
    requested_by_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_facts: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    approved_policy_version: Mapped[str | None] = mapped_column(String(100))
