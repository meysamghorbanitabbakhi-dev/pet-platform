"""Knowledge review lifecycle and operator task queue.

Revision ID: 20260716_0013
Revises: 20260716_0012
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0013"
down_revision: str | None = "20260716_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_pet_knowledge_releases_valid_status"),
        "pet_knowledge_releases",
        type_="check",
    )
    op.create_check_constraint(
        "valid_status",
        "pet_knowledge_releases",
        "status IN ('validated','imported','published','superseded','rejected','withdrawn',"
        "'review_expired')",
    )
    op.add_column(
        "pet_knowledge_reviews", sa.Column("expired_at", sa.DateTime(timezone=True))
    )
    op.create_table(
        "pet_knowledge_review_tasks",
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('due','expired','resolved')",
            name="ck_pet_knowledge_review_tasks_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"], ["pet_knowledge_reviews.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_knowledge_review_tasks"),
        sa.UniqueConstraint(
            "review_id", name="uq_pet_knowledge_review_tasks_one_task_per_review"
        ),
    )
    op.create_index(
        "ix_pet_knowledge_review_tasks_review_id",
        "pet_knowledge_review_tasks",
        ["review_id"],
    )
    op.create_index(
        "ix_pet_knowledge_review_tasks_due_at",
        "pet_knowledge_review_tasks",
        ["due_at"],
    )


def downgrade() -> None:
    op.drop_table("pet_knowledge_review_tasks")
    op.drop_column("pet_knowledge_reviews", "expired_at")
    op.drop_constraint(
        op.f("ck_pet_knowledge_releases_valid_status"),
        "pet_knowledge_releases",
        type_="check",
    )
    op.create_check_constraint(
        "valid_status",
        "pet_knowledge_releases",
        "status IN ('validated','imported','published','superseded','rejected','withdrawn')",
    )
