"""Shelf-life exceptions (Workstream 2E).

Revision ID: 20260719_0032
Revises: 20260719_0031

orders_order_lines gains excluded_from_delivery_at: set when a shelf-life
exception for that line is declined or expires unanswered, so
project_delivered_order (which otherwise requires SourcedUnitEvidence for
every line in the order) skips it instead of blocking the *other* lines
in the same order forever waiting for evidence that will never exist.

orders_shelf_life_exceptions: at most one per order line. Refunds are
operator-attested, same shape and same explicit product decision as
orders_cancellations (Workstream 2B) -- no automatic payment-gateway
reversal.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0032"
down_revision: str | None = "20260719_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ORDER_LINES = "orders_order_lines"
_EXCEPTIONS = "orders_shelf_life_exceptions"


def upgrade() -> None:
    op.add_column(
        _ORDER_LINES,
        sa.Column("excluded_from_delivery_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        _EXCEPTIONS,
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
            "order_line_id", sa.Uuid(), sa.ForeignKey("orders_order_lines.id"), nullable=False
        ),
        sa.Column("proposed_exact_expiry_date", sa.Date(), nullable=False),
        sa.Column(
            "additional_discount_irr", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "evidence_file_id", sa.Uuid(), sa.ForeignKey("trust_evidence_files.id"), nullable=False
        ),
        sa.Column(
            "proposed_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=False,
        ),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("respond_by", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "responded_by_customer_identity_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column(
            "refund_status", sa.String(20), nullable=False, server_default="not_applicable"
        ),
        sa.Column("refund_amount_irr", sa.Integer(), nullable=True),
        sa.Column("refund_attested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "refund_attested_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column(
            "refund_evidence_file_id",
            sa.Uuid(),
            sa.ForeignKey("trust_evidence_files.id"),
            nullable=True,
        ),
        sa.Column("refund_reference", sa.String(300), nullable=True),
        sa.UniqueConstraint("order_line_id", name="one_exception_per_order_line"),
    )
    op.create_index("ix_orders_shelf_life_exceptions_order_line_id", _EXCEPTIONS, ["order_line_id"])
    # The expiry sweep scans for status='proposed' rows past their
    # deadline; a composite index serves that query directly.
    op.create_index(
        "ix_orders_shelf_life_exceptions_status_respond_by",
        _EXCEPTIONS,
        ["status", "respond_by"],
    )
    op.create_check_constraint(
        "valid_status",
        _EXCEPTIONS,
        "status IN ('proposed','accepted','declined','expired')",
    )
    op.create_check_constraint(
        "nonnegative_discount", _EXCEPTIONS, "additional_discount_irr >= 0"
    )
    op.create_check_constraint(
        "valid_refund_status",
        _EXCEPTIONS,
        "refund_status IN ('not_applicable','owed','operator_attested')",
    )
    op.create_check_constraint(
        "positive_refund_amount",
        _EXCEPTIONS,
        "refund_amount_irr IS NULL OR refund_amount_irr > 0",
    )


def downgrade() -> None:
    op.drop_table(_EXCEPTIONS)
    op.drop_column(_ORDER_LINES, "excluded_from_delivery_at")
