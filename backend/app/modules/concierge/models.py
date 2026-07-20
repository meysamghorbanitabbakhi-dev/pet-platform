from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ConciergeOffer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One verified-offer cycle against a `CustomerRequest` of
    request_type='concierge_sourcing' (Workstream 4) -- the existing
    request stays the queue entry point; this is the offer lifecycle
    layered on top of it, gated behind settings.concierge_offers_enabled.

    An operator starts a cycle (status='reviewing'), verifies
    authenticity/source/landed price/delivery feasibility, and presents a
    payable offer (status='offer_presented') with either a reference-price
    savings framing or a landed-cost-plus-margin framing (Decision 0.34) --
    never both, and the landed-cost components are internal only, never
    serialized to a customer-facing response. The customer explicitly
    accepts (a real, full-payment Order is created lazily at accept time
    -- see accept_offer) or declines within `validity_hours` (12-48,
    default from settings.concierge_offer_default_validity_hours); an
    unanswered offer expires with no automatic re-verification (Decision
    0.36). A customer may request a refresh of an expired offer, which
    creates a *new* row (refreshed_from_offer_id) rather than reactivating
    the old one -- the old row's own fields are never mutated again once
    terminal.
    """

    __tablename__ = "concierge_offers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('reviewing','offer_presented','accepted','declined','expired',"
            "'unavailable','refresh_requested')",
            name="valid_status",
        ),
        CheckConstraint(
            "pricing_mode IS NULL OR "
            "pricing_mode IN ('reference_price_savings','landed_cost_plus_margin')",
            name="valid_pricing_mode",
        ),
        CheckConstraint("price_irr IS NULL OR price_irr > 0", name="positive_price"),
        CheckConstraint(
            "reference_price_irr IS NULL OR reference_price_irr > 0",
            name="positive_reference_price",
        ),
        CheckConstraint(
            "validity_hours IS NULL OR (validity_hours >= 12 AND validity_hours <= 48)",
            name="valid_validity_hours",
        ),
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint(
            "minimum_shelf_life_months IS NULL OR minimum_shelf_life_months > 0",
            name="positive_shelf_life",
        ),
        CheckConstraint(
            "estimated_delivery_days IS NULL OR estimated_delivery_days > 0",
            name="positive_delivery_days",
        ),
    )

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("support_customer_requests.id"), index=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("households_households.id"), index=True, nullable=False
    )
    customer_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True, nullable=False
    )
    # Set only when this row exists because the customer asked to refresh a
    # prior, expired offer (Decision 0.36) -- the referenced row's own
    # fields are never mutated once terminal.
    refreshed_from_offer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("concierge_offers.id")
    )
    status: Mapped[str] = mapped_column(String(20), default="reviewing", nullable=False)
    # Null until an operator actually starts reviewing -- for a
    # customer-created 'refresh_requested' row, that happens after
    # creation, not at it.
    reviewing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewing_started_by_operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )

    # Verification + description -- set when the offer is presented.
    title_fa: Mapped[str | None] = mapped_column(String(300))
    unit_label_fa: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    authenticity_basis: Mapped[str | None] = mapped_column(String(50))
    # Supplier country is customer-visible (via supplier.country_code);
    # supplier identity itself never is -- see ConciergeOfferResponse.
    supplier_id: Mapped[UUID | None] = mapped_column(ForeignKey("catalog_suppliers.id"))
    verification_evidence_file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("trust_evidence_files.id")
    )
    minimum_shelf_life_months: Mapped[int | None] = mapped_column(Integer)
    estimated_delivery_days: Mapped[int | None] = mapped_column(Integer)

    # Pricing -- set when the offer is presented (Decision 0.34).
    pricing_mode: Mapped[str | None] = mapped_column(String(30))
    price_irr: Mapped[int | None] = mapped_column(Integer)
    reference_price_irr: Mapped[int | None] = mapped_column(Integer)
    price_explanation_fa: Mapped[str | None] = mapped_column(Text)
    # Internal landed-cost components (landed_cost_plus_margin mode only).
    # NEVER serialize any of these nine fields in a customer-facing
    # response -- app/api/contracts.py keeps a separate
    # ConciergeOfferOperatorResponse for operator-only reads.
    supplier_cost_irr: Mapped[int | None] = mapped_column(Integer)
    exchange_rate_basis_irr_per_unit: Mapped[int | None] = mapped_column(Integer)
    international_transport_irr: Mapped[int | None] = mapped_column(Integer)
    customs_clearance_irr: Mapped[int | None] = mapped_column(Integer)
    handling_irr: Mapped[int | None] = mapped_column(Integer)
    domestic_delivery_irr: Mapped[int | None] = mapped_column(Integer)
    payment_fees_irr: Mapped[int | None] = mapped_column(Integer)
    risk_reserve_irr: Mapped[int | None] = mapped_column(Integer)
    platform_margin_irr: Mapped[int | None] = mapped_column(Integer)

    # Validity (Decision 0.35: 12-48h, default 24h, exact timestamp, price
    # locked for the window, re-verification required after expiry).
    presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    presented_by_operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    validity_hours: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Customer response.
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_by_customer_identity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    decline_reason: Mapped[str | None] = mapped_column(Text)

    # Operator "cannot source this" determination (skips presenting an
    # offer entirely, mirroring reserve-now's operator_declined).
    unavailable_reason: Mapped[str | None] = mapped_column(Text)
    unavailable_by_operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )

    # Acceptance creates a real, full-payment Order lazily (see
    # accept_offer) via a one-off Product/Offer(mode='concierge_only')
    # pair, hidden from catalog browse/search until an operator
    # deliberately promotes it (Decision 0.37).
    promoted_offer_id: Mapped[UUID | None] = mapped_column(ForeignKey("catalog_offers.id"))
    resulting_order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders_orders.id"))
    catalog_promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    catalog_promoted_by_operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    catalog_promotion_rationale: Mapped[str | None] = mapped_column(Text)


class ConciergeOfferEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only status history, mirroring the purchasing-batch,
    reservation, and replenishment-reservation event patterns."""

    __tablename__ = "concierge_offer_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('reviewing_started','offer_presented','accepted','declined',"
            "'expired','marked_unavailable','refresh_requested','catalog_promoted')",
            name="valid_event_type",
        ),
    )

    offer_id: Mapped[UUID] = mapped_column(
        ForeignKey("concierge_offers.id"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    operator_identity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    customer_identity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
