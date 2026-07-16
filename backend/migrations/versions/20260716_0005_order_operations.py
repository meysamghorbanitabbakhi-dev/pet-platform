"""Order operations and policy-gated resolutions.

Revision ID: 20260716_0005
Revises: 20260716_0004
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0005"
down_revision: str | None = "20260716_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orders_resolutions",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("resolution_type", sa.String(30), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("requested_by_operator_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("proposed_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("approved_policy_version", sa.String(100)),
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
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "resolution_type IN ('refund','replacement','substitution')",
            name="ck_orders_resolutions_valid_resolution_type",
        ),
        sa.CheckConstraint(
            "state IN ('awaiting_policy','approved','rejected','executed')",
            name="ck_orders_resolutions_valid_state",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders_orders.id"], name="fk_order_resolution_order"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_operator_id"],
            ["identity_auth_identities.id"],
            name="fk_order_resolution_operator",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_orders_resolutions"),
    )
    op.create_index("ix_orders_resolutions_order_id", "orders_resolutions", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_resolutions_order_id", table_name="orders_resolutions")
    op.drop_table("orders_resolutions")
