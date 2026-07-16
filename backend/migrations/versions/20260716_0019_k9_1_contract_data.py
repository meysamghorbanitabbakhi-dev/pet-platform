"""K9.1 catalog media and order-line pet plans.

Revision ID: 20260716_0019
Revises: 20260716_0018
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0019"
down_revision: str | None = "20260716_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("catalog_products", sa.Column("nominal_quantity_grams", sa.Integer()))
    op.create_check_constraint(
        "positive_nominal_quantity",
        "catalog_products",
        "nominal_quantity_grams IS NULL OR nominal_quantity_grams > 0",
    )
    op.create_table(
        "catalog_product_media",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("media_type", sa.String(20), nullable=False),
        sa.Column("public_reference", sa.String(500), nullable=False),
        sa.Column("alt_text_fa", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
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
        sa.CheckConstraint("media_type IN ('image','video')", name="valid_media_type"),
        sa.CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        sa.ForeignKeyConstraint(["product_id"], ["catalog_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "sort_order", name="product_media_sort_order"),
    )
    op.create_index("ix_catalog_product_media_product_id", "catalog_product_media", ["product_id"])
    op.create_table(
        "orders_order_line_pet_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_line_id", sa.Uuid(), nullable=False),
        sa.Column("pet_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["order_line_id"], ["orders_order_lines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pet_id"], ["pets_pets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_line_id", "pet_id", name="order_line_pet"),
    )
    op.create_index(
        "ix_orders_order_line_pet_plans_order_line_id",
        "orders_order_line_pet_plans",
        ["order_line_id"],
    )
    op.create_index(
        "ix_orders_order_line_pet_plans_pet_id", "orders_order_line_pet_plans", ["pet_id"]
    )


def downgrade() -> None:
    op.drop_table("orders_order_line_pet_plans")
    op.drop_table("catalog_product_media")
    op.drop_constraint("positive_nominal_quantity", "catalog_products", type_="check")
    op.drop_column("catalog_products", "nominal_quantity_grams")
