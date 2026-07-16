from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SupplierAssurance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trust_supplier_assurances"
    __table_args__ = (UniqueConstraint("supplier_id", "version", name="supplier_version"),)

    supplier_id: Mapped[UUID] = mapped_column(ForeignKey("catalog_suppliers.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_path: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recorded_by_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), nullable=False
    )


class ReferencePriceEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trust_reference_price_evidence"

    offer_id: Mapped[UUID] = mapped_column(ForeignKey("catalog_offers.id"), index=True)
    amount_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_label: Mapped[str] = mapped_column(String(300), nullable=False)
    evidence_path: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_by_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), nullable=False
    )


class SourcedUnitEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trust_sourced_unit_evidence"

    order_line_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders_order_lines.id"), unique=True, nullable=False
    )
    exact_expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_country_snapshot: Mapped[str] = mapped_column(String(2), nullable=False)
    authenticity_basis: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_assurance_id: Mapped[UUID] = mapped_column(
        ForeignKey("trust_supplier_assurances.id"), nullable=False
    )
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), nullable=False
    )
