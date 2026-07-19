"""Anonymous veterinary review and safe knowledge publication.

Revision ID: 20260716_0012
Revises: 20260716_0011
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0012"
down_revision: str | None = "20260716_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_pet_knowledge_releases_valid_status",
        "pet_knowledge_releases",
        type_="check",
    )
    op.create_check_constraint(
        "valid_status",
        "pet_knowledge_releases",
        "status IN ('validated','imported','published','superseded','rejected','withdrawn')",
    )
    op.add_column(
        "pet_knowledge_releases", sa.Column("published_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "pet_knowledge_releases", sa.Column("withdrawn_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "pet_knowledge_releases", sa.Column("supersedes_release_id", sa.Uuid())
    )
    op.create_foreign_key(
        "fk_knowledge_release_supersedes",
        "pet_knowledge_releases",
        "pet_knowledge_releases",
        ["supersedes_release_id"],
        ["id"],
    )
    op.create_index(
        "uq_pet_knowledge_one_published_release",
        "pet_knowledge_releases",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )
    op.drop_constraint(
        "ck_pet_knowledge_claims_not_publishable_during_ingestion",
        "pet_knowledge_claims",
        type_="check",
    )
    op.create_check_constraint(
        "eligible_requires_veterinary_approval",
        "pet_knowledge_claims",
        "app_eligible = false OR review_status = 'veterinary_approved'",
    )
    op.create_table(
        "pet_knowledge_reviews",
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid()),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reviewer_disclosure", sa.String(50), nullable=False),
        sa.Column("reviewed_checksum_sha256", sa.String(64), nullable=False),
        sa.Column("evidence_file_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_by_operator_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True)),
        sa.Column("limitations_fa", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "scope IN ('claim','release')",
            name="ck_pet_knowledge_reviews_valid_scope",
        ),
        sa.CheckConstraint(
            "decision IN ('approved','rejected')",
            name="ck_pet_knowledge_reviews_valid_decision",
        ),
        sa.CheckConstraint(
            "reviewer_disclosure = 'anonymous_external_veterinarian'",
            name="ck_pet_knowledge_reviews_anonymous_reviewer_only",
        ),
        sa.CheckConstraint(
            "(scope = 'claim' AND claim_id IS NOT NULL) OR "
            "(scope = 'release' AND claim_id IS NULL)",
            name="ck_pet_knowledge_reviews_valid_scope_target",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["pet_knowledge_releases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["pet_knowledge_claims.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["evidence_file_id"], ["trust_evidence_files.id"]),
        sa.ForeignKeyConstraint(["recorded_by_operator_id"], ["identity_auth_identities.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_pet_knowledge_reviews"),
    )
    op.create_index(
        "ix_pet_knowledge_reviews_release_id", "pet_knowledge_reviews", ["release_id"]
    )
    op.create_index("ix_pet_knowledge_reviews_claim_id", "pet_knowledge_reviews", ["claim_id"])
    op.create_index(
        "ix_pet_knowledge_reviews_recorded_by_operator_id",
        "pet_knowledge_reviews",
        ["recorded_by_operator_id"],
    )


def downgrade() -> None:
    op.drop_table("pet_knowledge_reviews")
    op.drop_constraint(
        "ck_pet_knowledge_claims_eligible_requires_veterinary_approval",
        "pet_knowledge_claims",
        type_="check",
    )
    op.create_check_constraint(
        "not_publishable_during_ingestion",
        "pet_knowledge_claims",
        "app_eligible = false",
    )
    op.drop_index(
        "uq_pet_knowledge_one_published_release", table_name="pet_knowledge_releases"
    )
    op.drop_constraint(
        "fk_knowledge_release_supersedes",
        "pet_knowledge_releases",
        type_="foreignkey",
    )
    op.drop_column("pet_knowledge_releases", "supersedes_release_id")
    op.drop_column("pet_knowledge_releases", "withdrawn_at")
    op.drop_column("pet_knowledge_releases", "published_at")
    op.drop_constraint(
        "ck_pet_knowledge_releases_valid_status",
        "pet_knowledge_releases",
        type_="check",
    )
    op.create_check_constraint(
        "valid_status",
        "pet_knowledge_releases",
        "status IN ('validated','imported','superseded','rejected')",
    )
