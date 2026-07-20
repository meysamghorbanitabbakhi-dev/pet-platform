"""Concierge verified-offer lifecycle (Workstream 4).

Revision ID: 20260720_0035
Revises: 20260719_0034

concierge_offers / concierge_offer_events: the offer lifecycle layered on
top of an existing support_customer_requests row (request_type=
'concierge_sourcing'), gated behind settings.concierge_offers_enabled=False
by default. catalog_offers.mode gains 'concierge_only', used only for the
one-off Offer/Product pair lazily created when a concierge offer is
accepted -- excluded from catalog browse/search until an operator
deliberately promotes it (Decision 0.37).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0035"
down_revision: str | None = "20260719_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OFFERS = "catalog_offers"
_CONCIERGE = "concierge_offers"
_EVENTS = "concierge_offer_events"


def upgrade() -> None:
    op.drop_constraint("valid_mode", _OFFERS, type_="check")
    op.create_check_constraint(
        "valid_mode", _OFFERS, "mode IN ('full_payment','reserve','concierge_only')"
    )

    op.create_table(
        _CONCIERGE,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            sa.Uuid(),
            sa.ForeignKey("support_customer_requests.id"),
            nullable=False,
        ),
        sa.Column(
            "household_id", sa.Uuid(), sa.ForeignKey("households_households.id"), nullable=False
        ),
        sa.Column(
            "customer_identity_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=False,
        ),
        sa.Column("refreshed_from_offer_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="reviewing"),
        sa.Column("reviewing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewing_started_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column("title_fa", sa.String(300), nullable=True),
        sa.Column("unit_label_fa", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("authenticity_basis", sa.String(50), nullable=True),
        sa.Column("supplier_id", sa.Uuid(), sa.ForeignKey("catalog_suppliers.id"), nullable=True),
        sa.Column(
            "verification_evidence_file_id",
            sa.Uuid(),
            sa.ForeignKey("trust_evidence_files.id"),
            nullable=True,
        ),
        sa.Column("minimum_shelf_life_months", sa.Integer(), nullable=True),
        sa.Column("estimated_delivery_days", sa.Integer(), nullable=True),
        sa.Column("pricing_mode", sa.String(30), nullable=True),
        sa.Column("price_irr", sa.Integer(), nullable=True),
        sa.Column("reference_price_irr", sa.Integer(), nullable=True),
        sa.Column("price_explanation_fa", sa.Text(), nullable=True),
        sa.Column("supplier_cost_irr", sa.Integer(), nullable=True),
        sa.Column("exchange_rate_basis_irr_per_unit", sa.Integer(), nullable=True),
        sa.Column("international_transport_irr", sa.Integer(), nullable=True),
        sa.Column("customs_clearance_irr", sa.Integer(), nullable=True),
        sa.Column("handling_irr", sa.Integer(), nullable=True),
        sa.Column("domestic_delivery_irr", sa.Integer(), nullable=True),
        sa.Column("payment_fees_irr", sa.Integer(), nullable=True),
        sa.Column("risk_reserve_irr", sa.Integer(), nullable=True),
        sa.Column("platform_margin_irr", sa.Integer(), nullable=True),
        sa.Column("presented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "presented_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column("validity_hours", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "responded_by_customer_identity_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("unavailable_reason", sa.Text(), nullable=True),
        sa.Column(
            "unavailable_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column(
            "promoted_offer_id", sa.Uuid(), sa.ForeignKey("catalog_offers.id"), nullable=True
        ),
        sa.Column("resulting_order_id", sa.Uuid(), sa.ForeignKey("orders_orders.id"), nullable=True),
        sa.Column("catalog_promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "catalog_promoted_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column("catalog_promotion_rationale", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "concierge_offers_refreshed_from_offer_id_fkey",
        _CONCIERGE,
        _CONCIERGE,
        ["refreshed_from_offer_id"],
        ["id"],
    )
    op.create_index("ix_concierge_offers_request_id", _CONCIERGE, ["request_id"])
    op.create_index("ix_concierge_offers_household_id", _CONCIERGE, ["household_id"])
    op.create_index(
        "ix_concierge_offers_customer_identity_id", _CONCIERGE, ["customer_identity_id"]
    )
    # The scheduler's expiry sweep scans by (status, expires_at).
    op.create_index(
        "ix_concierge_offers_status_expires", _CONCIERGE, ["status", "expires_at"]
    )
    op.create_check_constraint(
        "valid_status",
        _CONCIERGE,
        "status IN ('reviewing','offer_presented','accepted','declined','expired',"
        "'unavailable','refresh_requested')",
    )
    op.create_check_constraint(
        "valid_pricing_mode",
        _CONCIERGE,
        "pricing_mode IS NULL OR "
        "pricing_mode IN ('reference_price_savings','landed_cost_plus_margin')",
    )
    op.create_check_constraint("positive_price", _CONCIERGE, "price_irr IS NULL OR price_irr > 0")
    op.create_check_constraint(
        "positive_reference_price",
        _CONCIERGE,
        "reference_price_irr IS NULL OR reference_price_irr > 0",
    )
    op.create_check_constraint(
        "valid_validity_hours",
        _CONCIERGE,
        "validity_hours IS NULL OR (validity_hours >= 12 AND validity_hours <= 48)",
    )
    op.create_check_constraint("positive_quantity", _CONCIERGE, "quantity > 0")
    op.create_check_constraint(
        "positive_shelf_life",
        _CONCIERGE,
        "minimum_shelf_life_months IS NULL OR minimum_shelf_life_months > 0",
    )
    op.create_check_constraint(
        "positive_delivery_days",
        _CONCIERGE,
        "estimated_delivery_days IS NULL OR estimated_delivery_days > 0",
    )

    op.create_table(
        _EVENTS,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("offer_id", sa.Uuid(), sa.ForeignKey("concierge_offers.id"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "operator_identity_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column(
            "customer_identity_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_concierge_offer_events_offer_id", _EVENTS, ["offer_id"])
    op.create_check_constraint(
        "valid_event_type",
        _EVENTS,
        "event_type IN ('reviewing_started','offer_presented','accepted','declined',"
        "'expired','marked_unavailable','refresh_requested','catalog_promoted')",
    )


def downgrade() -> None:
    op.drop_table(_EVENTS)
    op.drop_constraint(
        "concierge_offers_refreshed_from_offer_id_fkey", _CONCIERGE, type_="foreignkey"
    )
    op.drop_table(_CONCIERGE)
    op.drop_constraint("valid_mode", _OFFERS, type_="check")
    op.create_check_constraint("valid_mode", _OFFERS, "mode IN ('full_payment','reserve')")
