"""Purchasing cycles and batches (Workstream 2A).

Revision ID: 20260719_0030
Revises: 20260719_0029

New tables only; no existing data affected, no backfill required.

purchasing_batches: one row per aggregated-or-individual purchasing cycle
for one offer. committed_at/committed_by_operator_id/commitment_evidence_file_id
are the durable supplier financial-commitment fact (timestamp + evidence,
per ADR-003) that the customer cancellation boundary (Workstream 2B) reads
-- a bare status change is not sufficient by itself.

purchasing_batch_allocations: which batch a given order line's sourcing
belongs to. One allocation per order line (unique constraint), created once
at payment-verified time, never reassigned.

purchasing_batch_events: append-only status history, mirroring the existing
orders_fulfillment_events pattern for the order domain.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0030"
down_revision: str | None = "20260719_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BATCHES = "purchasing_batches"
_ALLOCATIONS = "purchasing_batch_allocations"
_EVENTS = "purchasing_batch_events"


def upgrade() -> None:
    op.create_table(
        _BATCHES,
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
            "offer_id", sa.Uuid(), sa.ForeignKey("catalog_offers.id"), nullable=False
        ),
        sa.Column("grouping_mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("minimum_viable_threshold_quantity", sa.Integer(), nullable=False),
        sa.Column("allocated_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("threshold_reached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "committed_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column(
            "commitment_evidence_file_id",
            sa.Uuid(),
            sa.ForeignKey("trust_evidence_files.id"),
            nullable=True,
        ),
        sa.Column("commitment_reference", sa.String(300), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancelled_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('open','committed','cancelled')",
            name="ck_purchasing_batches_valid_status",
        ),
        sa.CheckConstraint(
            "grouping_mode IN ('aggregated','individual')",
            name="ck_purchasing_batches_valid_grouping_mode",
        ),
        sa.CheckConstraint(
            "minimum_viable_threshold_quantity > 0",
            name="ck_purchasing_batches_positive_threshold_quantity",
        ),
        sa.CheckConstraint(
            "allocated_quantity >= 0",
            name="ck_purchasing_batches_nonnegative_allocated_quantity",
        ),
    )
    op.create_index(
        "ix_purchasing_batches_offer_id", _BATCHES, ["offer_id"]
    )
    # The allocation service looks up "the current open aggregated batch for
    # this offer" on every allocation; a composite index serves that query
    # directly instead of a full scan filtered by status.
    op.create_index(
        "ix_purchasing_batches_offer_status_mode",
        _BATCHES,
        ["offer_id", "status", "grouping_mode"],
    )
    # Concurrency safety for the allocation service's "find or create the
    # open aggregated batch for this offer" pattern: two concurrent
    # transactions that both see no open batch and both try to open one
    # must not succeed in creating two -- the second INSERT fails this
    # constraint and the service falls back to re-fetching the winner
    # (same try/flush/except IntegrityError pattern already used by
    # subscribe_offer_availability in app/api/routes/commerce.py).
    # Individual-mode batches are always newly created per order line and
    # are deliberately excluded from this constraint.
    op.create_index(
        "uq_purchasing_batches_one_open_aggregated_per_offer",
        _BATCHES,
        ["offer_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open' AND grouping_mode = 'aggregated'"),
    )

    op.create_table(
        _ALLOCATIONS,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "purchase_batch_id", sa.Uuid(), sa.ForeignKey("purchasing_batches.id"), nullable=False
        ),
        sa.Column(
            "order_line_id", sa.Uuid(), sa.ForeignKey("orders_order_lines.id"), nullable=False
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("allocated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("order_line_id", name="one_batch_per_order_line"),
        sa.CheckConstraint("quantity > 0", name="ck_purchasing_batch_allocations_positive_quantity"),
    )
    op.create_index(
        "ix_purchasing_batch_allocations_purchase_batch_id",
        _ALLOCATIONS,
        ["purchase_batch_id"],
    )

    op.create_table(
        _EVENTS,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "purchase_batch_id", sa.Uuid(), sa.ForeignKey("purchasing_batches.id"), nullable=False
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
        sa.CheckConstraint(
            "event_type IN ('opened','threshold_reached','committed','cancelled')",
            name="ck_purchasing_batch_events_valid_event_type",
        ),
    )
    op.create_index(
        "ix_purchasing_batch_events_purchase_batch_id", _EVENTS, ["purchase_batch_id"]
    )


def downgrade() -> None:
    op.drop_table(_EVENTS)
    op.drop_table(_ALLOCATIONS)
    op.drop_table(_BATCHES)
