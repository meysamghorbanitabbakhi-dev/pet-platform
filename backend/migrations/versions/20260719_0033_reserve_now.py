"""Reserve-now: offer mode and reservation domain (Workstream 2C).

Revision ID: 20260719_0033
Revises: 20260719_0032

catalog_offers gains mode ('full_payment' default | 'reserve'),
explicit and operator-set like sourcing_route -- never inferred.

reservations_reservations / reservations_events: the reserve-now domain
itself. Fully built and live at the code level but reachable only when
settings.reserve_now_enabled=True, which defaults to False -- see
ADR-008. No deposit/partial-payment column exists anywhere in this
schema; a reservation is zero-charge until it converts into a normal,
full-payment Order.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0033"
down_revision: str | None = "20260719_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OFFERS = "catalog_offers"
_RESERVATIONS = "reservations_reservations"
_EVENTS = "reservations_events"


def upgrade() -> None:
    op.add_column(
        _OFFERS,
        sa.Column("mode", sa.String(20), nullable=False, server_default="full_payment"),
    )
    op.create_check_constraint("valid_mode", _OFFERS, "mode IN ('full_payment','reserve')")

    op.create_table(
        _RESERVATIONS,
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
            "customer_identity_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=False,
        ),
        sa.Column(
            "household_id", sa.Uuid(), sa.ForeignKey("households_households.id"), nullable=False
        ),
        sa.Column("offer_id", sa.Uuid(), sa.ForeignKey("catalog_offers.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("requested_price_irr", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("operator_review_by", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="requested"),
        sa.Column("reconfirmed_price_irr", sa.Integer(), nullable=True),
        sa.Column("reconfirmed_available", sa.Boolean(), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "proposed_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column("proposal_reason", sa.Text(), nullable=True),
        sa.Column("customer_respond_by", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders_orders.id"), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "customer_identity_id", "idempotency_key", name="customer_reservation_key"
        ),
    )
    op.create_index("ix_reservations_reservations_customer_identity_id", _RESERVATIONS, ["customer_identity_id"])
    op.create_index("ix_reservations_reservations_offer_id", _RESERVATIONS, ["offer_id"])
    # The two expiry sweeps scan by (status, deadline) directly.
    op.create_index(
        "ix_reservations_reservations_status_review_by",
        _RESERVATIONS,
        ["status", "operator_review_by"],
    )
    op.create_index(
        "ix_reservations_reservations_status_respond_by",
        _RESERVATIONS,
        ["status", "customer_respond_by"],
    )
    op.create_check_constraint(
        "valid_status",
        _RESERVATIONS,
        "status IN ('requested','proposed','converted','customer_declined',"
        "'operator_declined','expired')",
    )
    op.create_check_constraint("positive_quantity", _RESERVATIONS, "quantity > 0")
    op.create_check_constraint(
        "positive_requested_price", _RESERVATIONS, "requested_price_irr > 0"
    )
    op.create_check_constraint(
        "positive_reconfirmed_price",
        _RESERVATIONS,
        "reconfirmed_price_irr IS NULL OR reconfirmed_price_irr > 0",
    )

    op.create_table(
        _EVENTS,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "reservation_id",
            sa.Uuid(),
            sa.ForeignKey("reservations_reservations.id"),
            nullable=False,
        ),
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
    op.create_index("ix_reservations_events_reservation_id", _EVENTS, ["reservation_id"])
    op.create_check_constraint(
        "valid_event_type",
        _EVENTS,
        "event_type IN ('requested','proposed','approved','customer_declined',"
        "'operator_declined','expired','converted')",
    )


def downgrade() -> None:
    op.drop_table(_EVENTS)
    op.drop_table(_RESERVATIONS)
    op.drop_constraint("valid_mode", _OFFERS, type_="check")
    op.drop_column(_OFFERS, "mode")
