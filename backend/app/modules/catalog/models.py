from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
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


class Supplier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_suppliers"

    internal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_products"
    __table_args__ = (
        CheckConstraint("status IN ('draft','active','retired')", name="valid_status"),
    )

    name_fa: Mapped[str] = mapped_column(String(300), nullable=False)
    description_fa: Mapped[str | None] = mapped_column(Text)
    nominal_quantity_grams: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)


class ProductMedia(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_product_media"
    __table_args__ = (
        CheckConstraint("media_type IN ('image','video')", name="valid_media_type"),
        CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        UniqueConstraint("product_id", "sort_order", name="product_media_sort_order"),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_products.id", ondelete="CASCADE"), index=True
    )
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)
    public_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text_fa: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Offer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_offers"
    __table_args__ = (
        CheckConstraint("price_irr > 0", name="positive_price"),
        CheckConstraint(
            "reference_price_irr IS NULL OR reference_price_irr > 0",
            name="positive_reference_price",
        ),
        CheckConstraint("status IN ('active','unavailable','retired')", name="valid_status"),
        CheckConstraint(
            "stock_posture IN ('sourced_after_payment','unavailable')", name="valid_stock_posture"
        ),
        CheckConstraint("minimum_shelf_life_months > 0", name="positive_shelf_life"),
        CheckConstraint(
            "max_pending_quantity IS NULL OR max_pending_quantity > 0",
            name="positive_capacity",
        ),
        CheckConstraint(
            "sourcing_capacity_status IN ('open','paused')", name="valid_capacity_status"
        ),
    )

    product_id: Mapped[UUID] = mapped_column(ForeignKey("catalog_products.id"), index=True)
    supplier_id: Mapped[UUID] = mapped_column(ForeignKey("catalog_suppliers.id"), index=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title_fa: Mapped[str] = mapped_column(String(300), nullable=False)
    unit_label_fa: Mapped[str] = mapped_column(String(100), nullable=False)
    price_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_price_irr: Mapped[int | None] = mapped_column(Integer)
    reference_price_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    stock_posture: Mapped[str] = mapped_column(
        String(30), default="sourced_after_payment", nullable=False
    )
    minimum_shelf_life_months: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    available_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_pending_quantity: Mapped[int | None] = mapped_column(Integer)
    sourcing_capacity_status: Mapped[str] = mapped_column(
        String(20), default="open", nullable=False
    )


class CatalogAvailabilitySubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_availability_subscriptions"
    __table_args__ = (
        CheckConstraint("status IN ('active','notified','cancelled')", name="valid_status"),
        UniqueConstraint(
            "identity_id",
            "offer_id",
            "activation_cycle",
            name="identity_offer_activation_cycle",
        ),
    )

    identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True, nullable=False
    )
    household_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("households_households.id"), index=True
    )
    offer_id: Mapped[UUID] = mapped_column(ForeignKey("catalog_offers.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    activation_cycle: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
