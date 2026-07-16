from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SourcingJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sourcing_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','committed','failed','cancelled')", name="valid_status"
        ),
        UniqueConstraint("order_id", name="one_job_per_order"),
    )

    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders_orders.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
