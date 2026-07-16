"""K10.0 runtime truth and async integrity.

Revision ID: 20260716_0023
Revises: 20260716_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0023"
down_revision: str | None = "20260716_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "system_outbox_events",
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
    )
    op.add_column(
        "system_outbox_events",
        sa.Column("disposition", sa.String(20), server_default="unregistered", nullable=False),
    )
    op.create_check_constraint(
        "valid_outbox_status",
        "system_outbox_events",
        "status IN ('pending','published','failed','dead_letter')",
    )
    op.create_check_constraint(
        "valid_outbox_disposition",
        "system_outbox_events",
        "disposition IN ('handler','audit_only','unregistered')",
    )
    op.add_column("orders_orders", sa.Column("checkout_request_hash", sa.String(64)))
    op.add_column("payments_attempts", sa.Column("request_hash", sa.String(64)))
    op.add_column("support_customer_requests", sa.Column("request_hash", sa.String(64)))
    op.add_column("orders_delay_acknowledgements", sa.Column("request_hash", sa.String(64)))
    op.add_column("journey_check_ins", sa.Column("request_hash", sa.String(64)))


def downgrade() -> None:
    op.drop_column("journey_check_ins", "request_hash")
    op.drop_column("orders_delay_acknowledgements", "request_hash")
    op.drop_column("support_customer_requests", "request_hash")
    op.drop_column("payments_attempts", "request_hash")
    op.drop_column("orders_orders", "checkout_request_hash")
    op.drop_constraint("valid_outbox_disposition", "system_outbox_events", type_="check")
    op.drop_constraint("valid_outbox_status", "system_outbox_events", type_="check")
    op.drop_column("system_outbox_events", "disposition")
    op.drop_column("system_outbox_events", "status")
