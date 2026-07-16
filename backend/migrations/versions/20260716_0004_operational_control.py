"""Operational control and wallet ledger.

Revision ID: 20260716_0004
Revises: 20260716_0003
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0004"
down_revision: str | None = "20260716_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.add_column("orders_orders", sa.Column("household_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_orders_orders_household_id_households_households",
        "orders_orders",
        "households_households",
        ["household_id"],
        ["id"],
    )
    op.create_index("ix_orders_orders_household_id", "orders_orders", ["household_id"])
    op.add_column("orders_orders", sa.Column("delivered_at", sa.DateTime(timezone=True)))
    op.create_table(
        "orders_fulfillment_events",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("operator_identity_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('sourcing_started','sourcing_failed','in_transit',"
            "'delayed','delivered','cancelled','resolution_recorded')",
            name="ck_orders_fulfillment_events_valid_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders_orders.id"], name="fk_fulfillment_event_order"
        ),
        sa.ForeignKeyConstraint(
            ["operator_identity_id"],
            ["identity_auth_identities.id"],
            name="fk_fulfillment_event_operator",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_orders_fulfillment_events"),
    )
    op.create_index(
        "ix_orders_fulfillment_events_order_id", "orders_fulfillment_events", ["order_id"]
    )
    op.create_table(
        "wallet_accounts",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_households.id"],
            ondelete="CASCADE",
            name="fk_wallet_account_household",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wallet_accounts"),
        sa.UniqueConstraint("household_id", name="uq_wallet_accounts_household_id"),
    )
    op.create_table(
        "wallet_credits",
        sa.Column("wallet_account_id", sa.Uuid(), nullable=False),
        sa.Column("original_amount_irr", sa.Integer(), nullable=False),
        sa.Column("remaining_amount_irr", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "original_amount_irr > 0", name="ck_wallet_credits_positive_original_amount"
        ),
        sa.CheckConstraint(
            "remaining_amount_irr >= 0", name="ck_wallet_credits_nonnegative_remaining_amount"
        ),
        sa.CheckConstraint(
            "remaining_amount_irr <= original_amount_irr",
            name="ck_wallet_credits_remaining_within_original",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_account_id"], ["wallet_accounts.id"], name="fk_wallet_credit_account"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wallet_credits"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_wallet_credits_source_once"),
    )
    op.create_index("ix_wallet_credits_wallet_account_id", "wallet_credits", ["wallet_account_id"])
    op.create_index("ix_wallet_credits_expires_at", "wallet_credits", ["expires_at"])
    op.create_table(
        "wallet_debits",
        sa.Column("wallet_account_id", sa.Uuid(), nullable=False),
        sa.Column("amount_irr", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("amount_irr > 0", name="ck_wallet_debits_positive_amount"),
        sa.ForeignKeyConstraint(
            ["wallet_account_id"], ["wallet_accounts.id"], name="fk_wallet_debit_account"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wallet_debits"),
        sa.UniqueConstraint("idempotency_key", name="uq_wallet_debits_idempotency_key"),
    )
    op.create_index("ix_wallet_debits_wallet_account_id", "wallet_debits", ["wallet_account_id"])
    op.create_table(
        "wallet_debit_allocations",
        sa.Column("wallet_debit_id", sa.Uuid(), nullable=False),
        sa.Column("wallet_credit_id", sa.Uuid(), nullable=False),
        sa.Column("amount_irr", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("amount_irr > 0", name="ck_wallet_debit_allocations_positive_amount"),
        sa.ForeignKeyConstraint(
            ["wallet_debit_id"],
            ["wallet_debits.id"],
            ondelete="CASCADE",
            name="fk_wallet_allocation_debit",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_credit_id"], ["wallet_credits.id"], name="fk_wallet_allocation_credit"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wallet_debit_allocations"),
        sa.UniqueConstraint(
            "wallet_debit_id", "wallet_credit_id", name="uq_wallet_debit_allocations_debit_credit"
        ),
    )
    op.create_index(
        "ix_wallet_debit_allocations_wallet_debit_id",
        "wallet_debit_allocations",
        ["wallet_debit_id"],
    )
    op.create_index(
        "ix_wallet_debit_allocations_wallet_credit_id",
        "wallet_debit_allocations",
        ["wallet_credit_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wallet_debit_allocations_wallet_credit_id", table_name="wallet_debit_allocations"
    )
    op.drop_index(
        "ix_wallet_debit_allocations_wallet_debit_id", table_name="wallet_debit_allocations"
    )
    op.drop_table("wallet_debit_allocations")
    op.drop_index("ix_wallet_debits_wallet_account_id", table_name="wallet_debits")
    op.drop_table("wallet_debits")
    op.drop_index("ix_wallet_credits_expires_at", table_name="wallet_credits")
    op.drop_index("ix_wallet_credits_wallet_account_id", table_name="wallet_credits")
    op.drop_table("wallet_credits")
    op.drop_table("wallet_accounts")
    op.drop_index("ix_orders_fulfillment_events_order_id", table_name="orders_fulfillment_events")
    op.drop_table("orders_fulfillment_events")
    op.drop_column("orders_orders", "delivered_at")
    op.drop_index("ix_orders_orders_household_id", table_name="orders_orders")
    op.drop_constraint(
        "fk_orders_orders_household_id_households_households",
        "orders_orders",
        type_="foreignkey",
    )
    op.drop_column("orders_orders", "household_id")
