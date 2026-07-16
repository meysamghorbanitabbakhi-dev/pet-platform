"""Gate B0 foundation tables.

Revision ID: 20260716_0001
Revises: None
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_auth_identities",
        sa.Column("identity_type", sa.String(length=20), nullable=False),
        sa.Column("mobile_e164", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "identity_type IN ('customer','operator')",
            name="ck_identity_auth_identities_valid_identity_type",
        ),
        sa.CheckConstraint(
            "status IN ('active','disabled')", name="ck_identity_auth_identities_valid_status"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identity_auth_identities"),
        sa.UniqueConstraint("mobile_e164", name="uq_identity_auth_identities_mobile_e164"),
    )
    op.create_table(
        "identity_otp_challenges",
        sa.Column("mobile_e164", sa.String(length=20), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("provider_reference", sa.String(length=255)),
        sa.Column("delivery_status", sa.String(length=20), nullable=False),
        sa.Column("delivery_error", sa.Text()),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_identity_otp_challenges_attempts_nonnegative"),
        sa.CheckConstraint(
            "max_attempts > 0", name="ck_identity_otp_challenges_max_attempts_positive"
        ),
        sa.CheckConstraint(
            "delivery_status IN ('pending','sent','failed')",
            name="ck_identity_otp_challenges_valid_delivery_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identity_otp_challenges"),
    )
    op.create_index(
        "ix_identity_otp_challenges_mobile_e164", "identity_otp_challenges", ["mobile_e164"]
    )
    op.create_table(
        "identity_auth_sessions",
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("user_agent", sa.Text()),
        sa.Column("source_ip", sa.String(length=64)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identity_auth_identities.id"],
            name="fk_identity_auth_sessions_identity_id_identity_auth_identities",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identity_auth_sessions"),
        sa.UniqueConstraint(
            "refresh_token_hash", name="uq_identity_auth_sessions_refresh_token_hash"
        ),
    )
    op.create_index(
        "ix_identity_auth_sessions_identity_id", "identity_auth_sessions", ["identity_id"]
    )

    op.create_table(
        "system_outbox_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=200), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_until", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_system_outbox_events_attempts_nonnegative"),
        sa.PrimaryKeyConstraint("id", name="pk_system_outbox_events"),
        sa.UniqueConstraint("event_id", name="uq_system_outbox_events_event_id"),
    )
    op.create_index(
        "ix_outbox_dispatchable",
        "system_outbox_events",
        ["published_at", "available_at", "claimed_until"],
    )
    op.create_index("ix_system_outbox_events_event_type", "system_outbox_events", ["event_type"])

    op.create_table(
        "system_webhook_inbox",
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=200)),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False),
        sa.Column("processing_status", sa.String(length=30), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "processing_status IN ('received','processed','rejected','failed')",
            name="ck_system_webhook_inbox_valid_processing_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_system_webhook_inbox"),
        sa.UniqueConstraint(
            "provider", "provider_event_id", name="uq_system_webhook_inbox_provider"
        ),
    )

    op.create_table(
        "system_idempotency_records",
        sa.Column("scope", sa.String(length=150), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("response_status", sa.Integer()),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
            "state IN ('processing','completed','failed')",
            name="ck_system_idempotency_records_valid_idempotency_state",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_system_idempotency_records"),
        sa.UniqueConstraint("scope", "idempotency_key", name="uq_system_idempotency_records_scope"),
    )
    op.create_index(
        "ix_system_idempotency_records_expires_at", "system_idempotency_records", ["expires_at"]
    )

    op.create_table(
        "system_operator_audit_log",
        sa.Column("operator_identity_id", sa.Uuid()),
        sa.Column("action", sa.String(length=200), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("before_facts", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("after_facts", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("source_ip", sa.String(length=64)),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_system_operator_audit_log"),
        sa.UniqueConstraint("sequence", name="uq_system_operator_audit_log_sequence"),
    )
    op.create_index(
        "ix_operator_audit_resource", "system_operator_audit_log", ["resource_type", "resource_id"]
    )
    op.create_index("ix_system_operator_audit_log_action", "system_operator_audit_log", ["action"])
    op.create_index(
        "ix_system_operator_audit_log_request_id", "system_operator_audit_log", ["request_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_system_operator_audit_log_request_id", table_name="system_operator_audit_log")
    op.drop_index("ix_system_operator_audit_log_action", table_name="system_operator_audit_log")
    op.drop_index("ix_operator_audit_resource", table_name="system_operator_audit_log")
    op.drop_table("system_operator_audit_log")
    op.drop_index(
        "ix_system_idempotency_records_expires_at", table_name="system_idempotency_records"
    )
    op.drop_table("system_idempotency_records")
    op.drop_table("system_webhook_inbox")
    op.drop_index("ix_system_outbox_events_event_type", table_name="system_outbox_events")
    op.drop_index("ix_outbox_dispatchable", table_name="system_outbox_events")
    op.drop_table("system_outbox_events")
    op.drop_index("ix_identity_auth_sessions_identity_id", table_name="identity_auth_sessions")
    op.drop_table("identity_auth_sessions")
    op.drop_index("ix_identity_otp_challenges_mobile_e164", table_name="identity_otp_challenges")
    op.drop_table("identity_otp_challenges")
    op.drop_table("identity_auth_identities")
