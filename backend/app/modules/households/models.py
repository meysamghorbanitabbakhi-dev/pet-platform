from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Household(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "households_households"

    name: Mapped[str] = mapped_column(String(200), nullable=False)


class HouseholdMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "households_memberships"
    __table_args__ = (UniqueConstraint("household_id", "identity_id", name="member"),)

    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("households_households.id", ondelete="CASCADE"), index=True
    )
    identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="owner", nullable=False)


class HouseholdAddress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "households_addresses"

    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("households_households.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    recipient_mobile_e164: Mapped[str] = mapped_column(String(20), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    address_line: Mapped[str] = mapped_column(String(1000), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
