"""Launch hardening and privacy request workflow.

Revision ID: 20260716_0008
Revises: 20260716_0007
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0008"
down_revision: str | None = "20260716_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_privacy_requests",
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("request_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("result_facts", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "request_type IN ('export','disable','anonymize')",
            name="ck_identity_privacy_requests_valid_request_type",
        ),
        sa.CheckConstraint(
            "status IN ('requested','awaiting_policy','completed','rejected')",
            name="ck_identity_privacy_requests_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["identity_id"], ["identity_auth_identities.id"],
            name="fk_identity_privacy_request_identity",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identity_privacy_requests"),
    )
    op.create_index(
        "ix_identity_privacy_requests_identity_id",
        "identity_privacy_requests",
        ["identity_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_identity_privacy_requests_identity_id",
        table_name="identity_privacy_requests",
    )
    op.drop_table("identity_privacy_requests")
