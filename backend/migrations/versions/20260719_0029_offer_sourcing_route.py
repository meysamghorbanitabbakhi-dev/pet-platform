"""Offer sourcing route and default batch threshold (Workstream 2A).

Revision ID: 20260719_0029
Revises: 20260719_0028

Adds sourcing_route ('aggregated' | 'individual', operator-set, never
inferred from price/category) and default_batch_threshold_quantity
(nullable -- see ADR-006 for the no-configured-default fallback) to
catalog_offers. Backfill-before-not-null: sourcing_route gets a server_default
of 'aggregated' so every existing row is populated as part of adding the
column, matching Decision 0.10's framing of aggregation as the normal route
and individual sourcing as the operator-flagged exception.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0029"
down_revision: str | None = "20260719_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "catalog_offers"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            "sourcing_route", sa.String(20), nullable=False, server_default="aggregated"
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column("default_batch_threshold_quantity", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "valid_sourcing_route",
        _TABLE,
        "sourcing_route IN ('aggregated','individual')",
    )
    op.create_check_constraint(
        "positive_default_batch_threshold",
        _TABLE,
        "default_batch_threshold_quantity IS NULL OR default_batch_threshold_quantity > 0",
    )


def downgrade() -> None:
    op.drop_constraint("positive_default_batch_threshold", _TABLE, type_="check")
    op.drop_constraint("valid_sourcing_route", _TABLE, type_="check")
    op.drop_column(_TABLE, "default_batch_threshold_quantity")
    op.drop_column(_TABLE, "sourcing_route")
