"""One active food estimate per inventory unit (Workstream 5A).

Revision ID: 20260720_0036
Revises: 20260720_0035

A PostgreSQL partial unique index enforces at the database level what
correct_estimate/exhaust_inventory already enforce at the application
level (retire the old active row before creating a new one): at most one
food_estimation_estimates row with status='active' per inventory_unit_id.
This is a backstop, not a behavior change -- no existing rows violate it
(verified against the live database before writing this migration), so
no data cleanup step is needed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0036"
down_revision: str | None = "20260720_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "food_estimation_estimates"
_INDEX = "one_active_estimate_per_unit"


def upgrade() -> None:
    op.create_index(
        _INDEX,
        _TABLE,
        ["inventory_unit_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name=_TABLE)
