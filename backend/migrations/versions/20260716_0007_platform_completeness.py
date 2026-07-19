"""Platform completeness capabilities.

Revision ID: 20260716_0007
Revises: 20260716_0006
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0007"
down_revision: str | None = "20260716_0006"
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
    op.create_table(
        "households_addresses",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("recipient_name", sa.String(200), nullable=False),
        sa.Column("recipient_mobile_e164", sa.String(20), nullable=False),
        sa.Column("province", sa.String(100), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("address_line", sa.String(1000), nullable=False),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_households.id"],
            ondelete="CASCADE",
            name="fk_household_address_household",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_households_addresses"),
    )
    op.create_index(
        "ix_households_addresses_household_id", "households_addresses", ["household_id"]
    )
    op.add_column(
        "orders_orders",
        sa.Column(
            "delivery_address_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
    )
    op.add_column("catalog_offers", sa.Column("available_from", sa.DateTime(timezone=True)))
    op.add_column("catalog_offers", sa.Column("available_until", sa.DateTime(timezone=True)))
    op.add_column("catalog_offers", sa.Column("max_pending_quantity", sa.Integer()))
    op.add_column(
        "catalog_offers",
        sa.Column("sourcing_capacity_status", sa.String(20), server_default="open", nullable=False),
    )
    op.create_check_constraint(
        "ck_catalog_offers_positive_capacity",
        "catalog_offers",
        "max_pending_quantity IS NULL OR max_pending_quantity > 0",
    )
    op.create_check_constraint(
        "ck_catalog_offers_valid_capacity_status",
        "catalog_offers",
        "sourcing_capacity_status IN ('open','paused')",
    )
    op.drop_constraint(
        "uq_notifications_notifications_event_source_recipient",
        "notifications_notifications",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_notifications_event_source_recipient_channel",
        "notifications_notifications",
        ["event_key", "source_id", "recipient_identity_id", "channel"],
    )
    op.add_column("notifications_notifications", sa.Column("read_at", sa.DateTime(timezone=True)))
    op.create_table(
        "trust_evidence_files",
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("original_filename", sa.String(300), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_by_operator_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["uploaded_by_operator_id"],
            ["identity_auth_identities.id"],
            name="fk_evidence_file_operator",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trust_evidence_files"),
        sa.UniqueConstraint("storage_key", name="uq_trust_evidence_files_storage_key"),
    )


def downgrade() -> None:
    op.drop_table("trust_evidence_files")
    op.drop_column("notifications_notifications", "read_at")
    op.drop_constraint(
        "uq_notifications_event_source_recipient_channel",
        "notifications_notifications",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_notifications_notifications_event_source_recipient",
        "notifications_notifications",
        ["event_key", "source_id", "recipient_identity_id"],
    )
    op.drop_constraint("ck_catalog_offers_valid_capacity_status", "catalog_offers", type_="check")
    op.drop_constraint("ck_catalog_offers_positive_capacity", "catalog_offers", type_="check")
    op.drop_column("catalog_offers", "sourcing_capacity_status")
    op.drop_column("catalog_offers", "max_pending_quantity")
    op.drop_column("catalog_offers", "available_until")
    op.drop_column("catalog_offers", "available_from")
    op.drop_column("orders_orders", "delivery_address_snapshot")
    op.drop_index("ix_households_addresses_household_id", table_name="households_addresses")
    op.drop_table("households_addresses")
