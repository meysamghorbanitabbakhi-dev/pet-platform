"""Typed notification destinations.

Revision ID: 20260718_0026
Revises: 20260717_0025

Adds destination_kind/destination_id to notifications_notifications so the
frontend can deep-link a notification to the order/inventory-unit/journey/
customer-request/offer it refers to, instead of parsing event_key strings to
guess a route (client-invented routing) or leaving every notification a
dead-end inbox row.

destination_kind defaults to 'none' at the column level (server_default),
so every notification created before this migration reads back with a
destination of {kind: "none", id: null} -- no backfill needed, and no
existing row is ever misrepresented as pointing somewhere it doesn't.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0026"
down_revision: str | None = "20260717_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "notifications_notifications"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("destination_kind", sa.String(20), server_default="none", nullable=False),
    )
    op.add_column(
        _TABLE,
        sa.Column("destination_id", sa.Uuid(), nullable=True),
    )
    op.create_check_constraint(
        "valid_notification_destination_kind",
        _TABLE,
        "destination_kind IN ('order','inventory_unit','journey','customer_request','offer','none')",
    )


def downgrade() -> None:
    op.drop_constraint("valid_notification_destination_kind", _TABLE, type_="check")
    op.drop_column(_TABLE, "destination_id")
    op.drop_column(_TABLE, "destination_kind")
