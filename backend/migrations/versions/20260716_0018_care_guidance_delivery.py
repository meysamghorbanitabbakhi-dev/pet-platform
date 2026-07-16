"""Dismissible personalized care guidance delivery.

Revision ID: 20260716_0018
Revises: 20260716_0017
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0018"
down_revision: str | None = "20260716_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pet_knowledge_guidance_preferences",
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("guidance_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("snoozed_until", sa.DateTime(timezone=True)),
        sa.Column("acted_by_identity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('dismissed','snoozed')",
            name="ck_pet_knowledge_guidance_preferences_valid_status",
        ),
        sa.CheckConstraint(
            "(status = 'dismissed' AND snoozed_until IS NULL) OR "
            "(status = 'snoozed' AND snoozed_until IS NOT NULL)",
            name="ck_pet_knowledge_guidance_preferences_valid_snooze_state",
        ),
        sa.ForeignKeyConstraint(["pet_id"], ["pets_pets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["guidance_id"], ["pet_knowledge_guidance.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["acted_by_identity_id"], ["identity_auth_identities.id"]
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_knowledge_guidance_preferences"),
        sa.UniqueConstraint(
            "pet_id", "guidance_id", name="uq_pet_knowledge_guidance_preferences_pet_guidance"
        ),
    )
    for column in ("pet_id", "guidance_id", "snoozed_until", "acted_by_identity_id"):
        op.create_index(
            f"ix_pet_knowledge_guidance_preferences_{column}",
            "pet_knowledge_guidance_preferences",
            [column],
        )


def downgrade() -> None:
    op.drop_table("pet_knowledge_guidance_preferences")
