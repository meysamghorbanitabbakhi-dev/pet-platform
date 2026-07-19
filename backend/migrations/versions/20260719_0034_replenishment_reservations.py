"""Replenishment reservations (Workstream 3).

Revision ID: 20260719_0034
Revises: 20260719_0033

replenishment_reservations / replenishment_reservation_events: a
system-proposed reorder for one inventory unit's depletion cycle, gated
behind settings.replenishment_reservation_enabled=False by default. At
most one reservation per inventory unit, ever (unique constraint) -- a
unit has exactly one "need window" from opened to exhausted.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0034"
down_revision: str | None = "20260719_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RESERVATIONS = "replenishment_reservations"
_EVENTS = "replenishment_reservation_events"


def upgrade() -> None:
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
            "household_id", sa.Uuid(), sa.ForeignKey("households_households.id"), nullable=False
        ),
        sa.Column("pet_id", sa.Uuid(), sa.ForeignKey("pets_pets.id"), nullable=True),
        sa.Column(
            "inventory_unit_id", sa.Uuid(), sa.ForeignKey("inventory_units.id"), nullable=False
        ),
        sa.Column(
            "product_id", sa.Uuid(), sa.ForeignKey("catalog_products.id"), nullable=False
        ),
        sa.Column("offer_id", sa.Uuid(), sa.ForeignKey("catalog_offers.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "source_food_estimate_id",
            sa.Uuid(),
            sa.ForeignKey("food_estimation_estimates.id"),
            nullable=False,
        ),
        sa.Column("predicted_depletion_low_days", sa.Integer(), nullable=False),
        sa.Column("predicted_depletion_high_days", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_approval"),
        sa.Column("approval_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resulting_order_id", sa.Uuid(), sa.ForeignKey("orders_orders.id"), nullable=True
        ),
        sa.UniqueConstraint("inventory_unit_id", name="one_reservation_per_unit"),
        sa.UniqueConstraint("idempotency_key", name="one_reservation_per_idempotency_key"),
    )
    op.create_index(
        "ix_replenishment_reservations_household_id", _RESERVATIONS, ["household_id"]
    )
    # The scheduler's expiry sweep scans by (status, approval_expires_at).
    op.create_index(
        "ix_replenishment_reservations_status_expires",
        _RESERVATIONS,
        ["status", "approval_expires_at"],
    )
    op.create_check_constraint(
        "valid_status",
        _RESERVATIONS,
        "status IN ('pending_approval','approved','declined','expired','invalidated')",
    )
    op.create_check_constraint("positive_quantity", _RESERVATIONS, "quantity > 0")
    op.create_check_constraint(
        "valid_depletion_range",
        _RESERVATIONS,
        "predicted_depletion_low_days >= 0 AND "
        "predicted_depletion_high_days >= predicted_depletion_low_days",
    )

    op.create_table(
        _EVENTS,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "reservation_id",
            sa.Uuid(),
            sa.ForeignKey("replenishment_reservations.id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "identity_id", sa.Uuid(), sa.ForeignKey("identity_auth_identities.id"), nullable=True
        ),
    )
    op.create_index(
        "ix_replenishment_reservation_events_reservation_id", _EVENTS, ["reservation_id"]
    )
    op.create_check_constraint(
        "valid_event_type",
        _EVENTS,
        "event_type IN ('created','refreshed','approved','declined','expired','invalidated')",
    )


def downgrade() -> None:
    op.drop_table(_EVENTS)
    op.drop_table(_RESERVATIONS)
