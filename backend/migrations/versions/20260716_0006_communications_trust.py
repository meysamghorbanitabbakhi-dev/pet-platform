"""Communications and trust evidence.

Revision ID: 20260716_0006
Revises: 20260716_0005
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0006"
down_revision: str | None = "20260716_0005"
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
        "catalog_offers",
        sa.Column("minimum_shelf_life_months", sa.Integer(), server_default="6", nullable=False),
    )
    op.create_check_constraint(
        "ck_catalog_offers_positive_shelf_life",
        "catalog_offers",
        "minimum_shelf_life_months > 0",
    )
    op.add_column("inventory_units", sa.Column("exact_expiry_date", sa.Date()))
    op.add_column("inventory_units", sa.Column("sourcing_confirmed_at", sa.DateTime(timezone=True)))
    op.add_column("inventory_units", sa.Column("supplier_country_snapshot", sa.String(2)))
    op.add_column("inventory_units", sa.Column("authenticity_basis", sa.String(50)))
    op.create_table(
        "trust_supplier_assurances",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("evidence_path", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("recorded_by_operator_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["catalog_suppliers.id"], name="fk_supplier_assurance_supplier"
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_operator_id"],
            ["identity_auth_identities.id"],
            name="fk_supplier_assurance_operator",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trust_supplier_assurances"),
        sa.UniqueConstraint(
            "supplier_id", "version", name="uq_trust_supplier_assurances_supplier_version"
        ),
    )
    op.create_index(
        "ix_trust_supplier_assurances_supplier_id", "trust_supplier_assurances", ["supplier_id"]
    )
    op.create_table(
        "trust_sourced_unit_evidence",
        sa.Column("order_line_id", sa.Uuid(), nullable=False),
        sa.Column("exact_expiry_date", sa.Date(), nullable=False),
        sa.Column("supplier_country_snapshot", sa.String(2), nullable=False),
        sa.Column("authenticity_basis", sa.String(50), nullable=False),
        sa.Column("supplier_assurance_id", sa.Uuid(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_operator_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_line_id"], ["orders_order_lines.id"], name="fk_sourced_evidence_order_line"
        ),
        sa.ForeignKeyConstraint(
            ["supplier_assurance_id"],
            ["trust_supplier_assurances.id"],
            name="fk_sourced_evidence_assurance",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_operator_id"],
            ["identity_auth_identities.id"],
            name="fk_sourced_evidence_operator",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trust_sourced_unit_evidence"),
        sa.UniqueConstraint("order_line_id", name="uq_trust_sourced_unit_evidence_order_line_id"),
    )
    op.create_table(
        "trust_reference_price_evidence",
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column("amount_irr", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_label", sa.String(300), nullable=False),
        sa.Column("evidence_path", sa.Text(), nullable=False),
        sa.Column("recorded_by_operator_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["offer_id"], ["catalog_offers.id"], name="fk_reference_evidence_offer"
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_operator_id"],
            ["identity_auth_identities.id"],
            name="fk_reference_evidence_operator",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trust_reference_price_evidence"),
    )
    op.create_index(
        "ix_trust_reference_price_evidence_offer_id", "trust_reference_price_evidence", ["offer_id"]
    )
    op.create_table(
        "notifications_preferences",
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("event_key", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("quiet_start_local", sa.Time()),
        sa.Column("quiet_end_local", sa.Time()),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identity_auth_identities.id"],
            name="fk_notification_preference_identity",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notifications_preferences"),
        sa.UniqueConstraint(
            "identity_id",
            "channel",
            "event_key",
            name="uq_notifications_preferences_identity_channel_event",
        ),
    )
    op.create_index(
        "ix_notifications_preferences_identity_id", "notifications_preferences", ["identity_id"]
    )
    op.create_table(
        "notifications_templates",
        sa.Column("event_key", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body_fa", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_notifications_templates"),
        sa.UniqueConstraint(
            "event_key",
            "channel",
            "version",
            name="uq_notifications_templates_event_channel_version",
        ),
    )
    op.create_table(
        "notifications_notifications",
        sa.Column("recipient_identity_id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','deferred','sent','failed','suppressed')",
            name="ck_notifications_notifications_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_identity_id"],
            ["identity_auth_identities.id"],
            name="fk_notification_recipient",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notifications_notifications"),
        sa.UniqueConstraint(
            "event_key",
            "source_id",
            "recipient_identity_id",
            name="uq_notifications_notifications_event_source_recipient",
        ),
    )
    op.create_index(
        "ix_notifications_notifications_recipient_identity_id",
        "notifications_notifications",
        ["recipient_identity_id"],
    )
    op.create_table(
        "notifications_attempts",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider_reference", sa.String(255)),
        sa.Column("error_code", sa.String(100)),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('sent','failed')", name="ck_notifications_attempts_valid_status"
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications_notifications.id"],
            ondelete="CASCADE",
            name="fk_notification_attempt_notification",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notifications_attempts"),
    )
    op.create_index(
        "ix_notifications_attempts_notification_id", "notifications_attempts", ["notification_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_attempts_notification_id", table_name="notifications_attempts")
    op.drop_table("notifications_attempts")
    op.drop_index(
        "ix_notifications_notifications_recipient_identity_id",
        table_name="notifications_notifications",
    )
    op.drop_table("notifications_notifications")
    op.drop_table("notifications_templates")
    op.drop_index(
        "ix_notifications_preferences_identity_id", table_name="notifications_preferences"
    )
    op.drop_table("notifications_preferences")
    op.drop_table("trust_sourced_unit_evidence")
    op.drop_index(
        "ix_trust_reference_price_evidence_offer_id", table_name="trust_reference_price_evidence"
    )
    op.drop_table("trust_reference_price_evidence")
    op.drop_index(
        "ix_trust_supplier_assurances_supplier_id", table_name="trust_supplier_assurances"
    )
    op.drop_table("trust_supplier_assurances")
    op.drop_column("inventory_units", "authenticity_basis")
    op.drop_column("inventory_units", "supplier_country_snapshot")
    op.drop_column("inventory_units", "sourcing_confirmed_at")
    op.drop_column("inventory_units", "exact_expiry_date")
    op.drop_constraint("ck_catalog_offers_positive_shelf_life", "catalog_offers", type_="check")
    op.drop_column("catalog_offers", "minimum_shelf_life_months")
