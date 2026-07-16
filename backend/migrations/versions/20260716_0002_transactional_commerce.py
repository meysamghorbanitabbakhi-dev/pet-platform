"""Transactional commerce foundation.

Revision ID: 20260716_0002
Revises: 20260716_0001
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0002"
down_revision: str | None = "20260716_0001"
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
    op.add_column(
        "identity_auth_sessions",
        sa.Column("access_token_hash", sa.String(128), nullable=False),
    )
    op.add_column(
        "identity_auth_sessions",
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_identity_auth_sessions_access_token_hash",
        "identity_auth_sessions",
        ["access_token_hash"],
    )
    op.create_table(
        "catalog_suppliers",
        sa.Column("internal_name", sa.String(200), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_suppliers"),
    )
    op.create_table(
        "catalog_products",
        sa.Column("name_fa", sa.String(300), nullable=False),
        sa.Column("description_fa", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','active','retired')", name="ck_catalog_products_valid_status"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_products"),
    )
    op.create_table(
        "catalog_offers",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("title_fa", sa.String(300), nullable=False),
        sa.Column("unit_label_fa", sa.String(100), nullable=False),
        sa.Column("price_irr", sa.Integer(), nullable=False),
        sa.Column("reference_price_irr", sa.Integer()),
        sa.Column("reference_price_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stock_posture", sa.String(30), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("price_irr > 0", name="ck_catalog_offers_positive_price"),
        sa.CheckConstraint(
            "reference_price_irr IS NULL OR reference_price_irr > 0",
            name="ck_catalog_offers_positive_reference_price",
        ),
        sa.CheckConstraint(
            "status IN ('active','unavailable','retired')", name="ck_catalog_offers_valid_status"
        ),
        sa.CheckConstraint(
            "stock_posture IN ('sourced_after_payment','unavailable')",
            name="ck_catalog_offers_valid_stock_posture",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["catalog_products.id"],
            name="fk_catalog_offers_product_id_catalog_products",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["catalog_suppliers.id"],
            name="fk_catalog_offers_supplier_id_catalog_suppliers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_offers"),
        sa.UniqueConstraint("sku", name="uq_catalog_offers_sku"),
    )
    op.create_index("ix_catalog_offers_product_id", "catalog_offers", ["product_id"])
    op.create_index("ix_catalog_offers_supplier_id", "catalog_offers", ["supplier_id"])
    op.create_table(
        "orders_orders",
        sa.Column("customer_identity_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("merchandise_total_irr", sa.Integer(), nullable=False),
        sa.Column("checkout_idempotency_key", sa.String(255), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("delivery_commitment_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('awaiting_payment','paid','sourcing','in_transit',"
            "'delivered','cancelled','failed')",
            name="ck_orders_orders_valid_status",
        ),
        sa.CheckConstraint("merchandise_total_irr > 0", name="ck_orders_orders_positive_total"),
        sa.CheckConstraint("currency = 'IRR'", name="ck_orders_orders_irr_only"),
        sa.ForeignKeyConstraint(
            ["customer_identity_id"],
            ["identity_auth_identities.id"],
            name="fk_orders_orders_customer_identity_id_identity_auth_identities",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_orders_orders"),
        sa.UniqueConstraint(
            "customer_identity_id",
            "checkout_idempotency_key",
            name="uq_orders_orders_customer_checkout_key",
        ),
    )
    op.create_index(
        "ix_orders_orders_customer_identity_id", "orders_orders", ["customer_identity_id"]
    )
    op.create_table(
        "orders_order_lines",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column("sku_snapshot", sa.String(100), nullable=False),
        sa.Column("title_fa_snapshot", sa.String(300), nullable=False),
        sa.Column("unit_label_fa_snapshot", sa.String(100), nullable=False),
        sa.Column("supplier_country_snapshot", sa.String(2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_irr", sa.Integer(), nullable=False),
        sa.Column("line_total_irr", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_orders_order_lines_positive_quantity"),
        sa.CheckConstraint("unit_price_irr > 0", name="ck_orders_order_lines_positive_unit_price"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["catalog_offers.id"],
            name="fk_orders_order_lines_offer_id_catalog_offers",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders_orders.id"],
            name="fk_orders_order_lines_order_id_orders_orders",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_orders_order_lines"),
    )
    op.create_index("ix_orders_order_lines_offer_id", "orders_order_lines", ["offer_id"])
    op.create_index("ix_orders_order_lines_order_id", "orders_order_lines", ["order_id"])
    op.create_table(
        "payments_attempts",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("amount_irr", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("provider_reference", sa.String(255)),
        sa.Column("provider_transaction_id", sa.String(255)),
        sa.Column("redirect_url", sa.Text()),
        sa.Column("masked_card", sa.String(64)),
        sa.Column("card_hash", sa.String(255)),
        sa.Column("fee_irr", sa.Integer()),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(100)),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("amount_irr > 0", name="ck_payments_attempts_positive_amount"),
        sa.CheckConstraint("currency = 'IRR'", name="ck_payments_attempts_irr_only"),
        sa.CheckConstraint(
            "status IN ('created','redirect_ready','verified','failed')",
            name="ck_payments_attempts_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders_orders.id"], name="fk_payments_attempts_order_id_orders_orders"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payments_attempts"),
        sa.UniqueConstraint(
            "order_id", "idempotency_key", name="uq_payments_attempts_order_payment_key"
        ),
        sa.UniqueConstraint(
            "provider", "provider_reference", name="uq_payments_attempts_provider_reference"
        ),
    )
    op.create_index("ix_payments_attempts_order_id", "payments_attempts", ["order_id"])
    op.create_table(
        "sourcing_jobs",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','committed','failed','cancelled')",
            name="ck_sourcing_jobs_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders_orders.id"], name="fk_sourcing_jobs_order_id_orders_orders"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sourcing_jobs"),
        sa.UniqueConstraint("order_id", name="uq_sourcing_jobs_one_job_per_order"),
    )


def downgrade() -> None:
    op.drop_table("sourcing_jobs")
    op.drop_index("ix_payments_attempts_order_id", table_name="payments_attempts")
    op.drop_table("payments_attempts")
    op.drop_index("ix_orders_order_lines_order_id", table_name="orders_order_lines")
    op.drop_index("ix_orders_order_lines_offer_id", table_name="orders_order_lines")
    op.drop_table("orders_order_lines")
    op.drop_index("ix_orders_orders_customer_identity_id", table_name="orders_orders")
    op.drop_table("orders_orders")
    op.drop_index("ix_catalog_offers_supplier_id", table_name="catalog_offers")
    op.drop_index("ix_catalog_offers_product_id", table_name="catalog_offers")
    op.drop_table("catalog_offers")
    op.drop_table("catalog_products")
    op.drop_table("catalog_suppliers")
    op.drop_constraint(
        "uq_identity_auth_sessions_access_token_hash",
        "identity_auth_sessions",
        type_="unique",
    )
    op.drop_column("identity_auth_sessions", "access_token_hash")
    op.drop_column("identity_auth_sessions", "access_expires_at")
