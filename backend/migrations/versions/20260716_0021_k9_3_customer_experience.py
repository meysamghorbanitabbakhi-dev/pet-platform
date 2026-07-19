"""K9.3 customer experience persistence.

Revision ID: 20260716_0021
Revises: 20260716_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260716_0021"
down_revision: str | None = "20260716_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_availability_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid()),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("activation_cycle", sa.Integer(), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active','notified','cancelled')", name="valid_status"),
        sa.ForeignKeyConstraint(["identity_id"], ["identity_auth_identities.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households_households.id"]),
        sa.ForeignKeyConstraint(["offer_id"], ["catalog_offers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_id", "offer_id", "activation_cycle", name="identity_offer_activation_cycle"),
    )
    op.create_index("ix_catalog_availability_subscriptions_identity_id", "catalog_availability_subscriptions", ["identity_id"])
    op.create_index("ix_catalog_availability_subscriptions_household_id", "catalog_availability_subscriptions", ["household_id"])
    op.create_index("ix_catalog_availability_subscriptions_offer_id", "catalog_availability_subscriptions", ["offer_id"])
    op.create_index(
        "uq_active_availability_subscription",
        "catalog_availability_subscriptions",
        ["identity_id", "offer_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "support_customer_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("request_type", sa.String(30), nullable=False),
        sa.Column("order_id", sa.Uuid()),
        sa.Column("offer_id", sa.Uuid()),
        sa.Column("product_query_fa", sa.String(500)),
        sa.Column("message_fa", sa.Text(), nullable=False),
        sa.Column("contact_preference", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("request_type IN ('support','concierge_sourcing')", name="valid_request_type"),
        sa.CheckConstraint("contact_preference IN ('in_app','sms')", name="valid_contact_preference"),
        sa.CheckConstraint("status IN ('submitted','in_review','resolved','closed')", name="valid_status"),
        sa.ForeignKeyConstraint(["identity_id"], ["identity_auth_identities.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households_households.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders_orders.id"]),
        sa.ForeignKeyConstraint(["offer_id"], ["catalog_offers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_id", "idempotency_key", name="identity_request_key"),
    )
    for column in ("identity_id", "household_id", "order_id", "offer_id"):
        op.create_index(f"ix_support_customer_requests_{column}", "support_customer_requests", [column])
    op.create_table(
        "support_customer_request_status_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("operator_identity_id", sa.Uuid()),
        sa.Column("old_status", sa.String(20)),
        sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("facts", JSONB(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["support_customer_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operator_identity_id"], ["identity_auth_identities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_customer_request_status_audit_request_id", "support_customer_request_status_audit", ["request_id"])
    op.create_index("ix_support_customer_request_status_audit_operator_identity_id", "support_customer_request_status_audit", ["operator_identity_id"])
    op.create_table(
        "orders_delay_acknowledgements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("delay_event_version", sa.Integer(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["identity_id"], ["identity_auth_identities.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_id", "order_id", "idempotency_key", name="identity_order_ack_key"),
        sa.UniqueConstraint("identity_id", "order_id", "delay_event_version", name="identity_order_delay_version"),
    )
    op.create_index("ix_orders_delay_acknowledgements_identity_id", "orders_delay_acknowledgements", ["identity_id"])
    op.create_index("ix_orders_delay_acknowledgements_order_id", "orders_delay_acknowledgements", ["order_id"])
    op.add_column("journeys_pet_journeys", sa.Column("definition_version", sa.Integer()))
    op.add_column("journeys_pet_journeys", sa.Column("definition_snapshot", JSONB()))
    op.add_column("journeys_pet_journeys", sa.Column("completion_effects_created_at", sa.DateTime(timezone=True)))
    op.create_table(
        "journey_check_ins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journey_id", sa.Uuid(), nullable=False),
        sa.Column("check_in_key", sa.String(100), nullable=False),
        sa.Column("answer_key", sa.String(100), nullable=False),
        sa.Column("submitted_by_identity_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["journey_id"], ["journeys_pet_journeys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by_identity_id"], ["identity_auth_identities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("journey_id", "check_in_key", name="journey_check_in_once"),
        sa.UniqueConstraint("journey_id", "idempotency_key", name="journey_check_in_key_once"),
    )
    op.create_index("ix_journey_check_ins_journey_id", "journey_check_ins", ["journey_id"])
    op.create_index("ix_journey_check_ins_submitted_by_identity_id", "journey_check_ins", ["submitted_by_identity_id"])


def downgrade() -> None:
    op.drop_table("journey_check_ins")
    op.drop_column("journeys_pet_journeys", "completion_effects_created_at")
    op.drop_column("journeys_pet_journeys", "definition_snapshot")
    op.drop_column("journeys_pet_journeys", "definition_version")
    op.drop_table("orders_delay_acknowledgements")
    op.drop_table("support_customer_request_status_audit")
    op.drop_table("support_customer_requests")
    op.drop_index("uq_active_availability_subscription", table_name="catalog_availability_subscriptions")
    op.drop_table("catalog_availability_subscriptions")
