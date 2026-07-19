"""Certified anonymous batch knowledge approval.

Revision ID: 20260716_0015
Revises: 20260716_0014
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0015"
down_revision: str | None = "20260716_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pet_knowledge_guidance",
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("breed_external_id", sa.String(150), nullable=False),
        sa.Column("variety_external_id", sa.String(150)),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("text_fa", sa.Text(), nullable=False),
        sa.Column("supporting_claim_external_ids", postgresql.JSONB(), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False),
        sa.Column("app_eligible", sa.Boolean(), nullable=False),
        sa.Column("record", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "review_status IN ('veterinary_review_required','veterinary_approved','rejected',"
            "'superseded','withdrawn')",
            name="ck_pet_knowledge_guidance_valid_review_status",
        ),
        sa.CheckConstraint(
            "app_eligible = false OR review_status = 'veterinary_approved'",
            name="ck_pet_knowledge_guidance_eligible_requires_veterinary_approval",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["pet_knowledge_releases.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_knowledge_guidance"),
        sa.UniqueConstraint(
            "release_id", "external_id", name="uq_pet_knowledge_guidance_release_external_id"
        ),
    )
    op.create_index("ix_pet_knowledge_guidance_release_id", "pet_knowledge_guidance", ["release_id"])
    op.create_index(
        "ix_pet_knowledge_guidance_breed_external_id",
        "pet_knowledge_guidance",
        ["breed_external_id"],
    )
    op.drop_constraint(
        "ck_pet_knowledge_reviews_valid_scope_target", "pet_knowledge_reviews", type_="check"
    )
    op.drop_constraint(
        "ck_pet_knowledge_reviews_valid_scope", "pet_knowledge_reviews", type_="check"
    )
    op.add_column("pet_knowledge_reviews", sa.Column("guidance_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_knowledge_review_guidance",
        "pet_knowledge_reviews",
        "pet_knowledge_guidance",
        ["guidance_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_pet_knowledge_reviews_guidance_id", "pet_knowledge_reviews", ["guidance_id"]
    )
    op.create_check_constraint(
        "valid_scope",
        "pet_knowledge_reviews",
        "scope IN ('claim','guidance','release')",
    )
    op.create_check_constraint(
        "valid_scope_target",
        "pet_knowledge_reviews",
        "(scope = 'claim' AND claim_id IS NOT NULL AND guidance_id IS NULL) OR "
        "(scope = 'guidance' AND guidance_id IS NOT NULL AND claim_id IS NULL) OR "
        "(scope = 'release' AND claim_id IS NULL AND guidance_id IS NULL)",
    )
    op.add_column(
        "pet_knowledge_reviews",
        sa.Column(
            "credential_verified_privately",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("pet_knowledge_reviews", "credential_verified_privately")
    op.drop_constraint(
        "ck_pet_knowledge_reviews_valid_scope_target", "pet_knowledge_reviews", type_="check"
    )
    op.drop_constraint(
        "ck_pet_knowledge_reviews_valid_scope", "pet_knowledge_reviews", type_="check"
    )
    op.drop_index("ix_pet_knowledge_reviews_guidance_id", table_name="pet_knowledge_reviews")
    op.drop_constraint("fk_knowledge_review_guidance", "pet_knowledge_reviews", type_="foreignkey")
    op.drop_column("pet_knowledge_reviews", "guidance_id")
    op.create_check_constraint(
        "valid_scope", "pet_knowledge_reviews", "scope IN ('claim','release')"
    )
    op.create_check_constraint(
        "valid_scope_target",
        "pet_knowledge_reviews",
        "(scope = 'claim' AND claim_id IS NOT NULL) OR "
        "(scope = 'release' AND claim_id IS NULL)",
    )
    op.drop_table("pet_knowledge_guidance")
