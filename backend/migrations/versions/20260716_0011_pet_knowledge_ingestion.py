"""Versioned pet knowledge ingestion.

Revision ID: 20260716_0011
Revises: 20260716_0010
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0011"
down_revision: str | None = "20260716_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "pet_knowledge_releases",
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("dataset_version", sa.String(50), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("imported_by_operator_id", sa.Uuid(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("breed_count", sa.Integer(), nullable=False),
        sa.Column("variety_count", sa.Integer(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("claim_count", sa.Integer(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("language = 'fa-IR'", name="ck_pet_knowledge_releases_persian_only"),
        sa.CheckConstraint(
            "status IN ('validated','imported','superseded','rejected')",
            name="ck_pet_knowledge_releases_valid_status",
        ),
        sa.ForeignKeyConstraint(["imported_by_operator_id"], ["identity_auth_identities.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_pet_knowledge_releases"),
        sa.UniqueConstraint(
            "dataset_version", name="uq_pet_knowledge_releases_dataset_version"
        ),
        sa.UniqueConstraint(
            "checksum_sha256", name="uq_pet_knowledge_releases_checksum_sha256"
        ),
        sa.UniqueConstraint("storage_key", name="uq_pet_knowledge_releases_storage_key"),
    )
    op.create_index(
        "ix_pet_knowledge_releases_imported_by_operator_id",
        "pet_knowledge_releases",
        ["imported_by_operator_id"],
    )

    op.create_table(
        "pet_knowledge_breeds",
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(150), nullable=False),
        sa.Column("species", sa.String(10), nullable=False),
        sa.Column("name_fa", sa.String(300), nullable=False),
        sa.Column("name_en", sa.String(300), nullable=False),
        sa.Column("record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "species IN ('dog','cat')", name="ck_pet_knowledge_breeds_valid_species"
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["pet_knowledge_releases.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_knowledge_breeds"),
        sa.UniqueConstraint(
            "release_id", "external_id", name="uq_pet_knowledge_breeds_release_external_id"
        ),
    )
    op.create_index(
        "ix_pet_knowledge_breeds_release_id", "pet_knowledge_breeds", ["release_id"]
    )

    op.create_table(
        "pet_knowledge_varieties",
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(150), nullable=False),
        sa.Column("breed_external_id", sa.String(150), nullable=False),
        sa.Column("name_fa", sa.String(300), nullable=False),
        sa.Column("name_en", sa.String(300), nullable=False),
        sa.Column("record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_id"], ["pet_knowledge_releases.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_knowledge_varieties"),
        sa.UniqueConstraint(
            "release_id",
            "external_id",
            name="uq_pet_knowledge_varieties_release_external_id",
        ),
    )
    op.create_index(
        "ix_pet_knowledge_varieties_release_id", "pet_knowledge_varieties", ["release_id"]
    )

    op.create_table(
        "pet_knowledge_sources",
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_id"], ["pet_knowledge_releases.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_knowledge_sources"),
        sa.UniqueConstraint(
            "release_id", "external_id", name="uq_pet_knowledge_sources_release_external_id"
        ),
    )
    op.create_index(
        "ix_pet_knowledge_sources_release_id", "pet_knowledge_sources", ["release_id"]
    )

    op.create_table(
        "pet_knowledge_claims",
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("breed_external_id", sa.String(150), nullable=False),
        sa.Column("variety_external_id", sa.String(150)),
        sa.Column("claim_type", sa.String(100), nullable=False),
        sa.Column("text_fa", sa.String(5000), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False),
        sa.Column("app_eligible", sa.Boolean(), nullable=False),
        sa.Column("record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "review_status IN "
            "('draft','editorial_reviewed','veterinary_review_required','veterinary_approved',"
            "'rejected','superseded','withdrawn')",
            name="ck_pet_knowledge_claims_valid_review_status",
        ),
        sa.CheckConstraint(
            "app_eligible = false",
            name="ck_pet_knowledge_claims_not_publishable_during_ingestion",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["pet_knowledge_releases.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_knowledge_claims"),
        sa.UniqueConstraint(
            "release_id", "external_id", name="uq_pet_knowledge_claims_release_external_id"
        ),
    )
    op.create_index(
        "ix_pet_knowledge_claims_release_id", "pet_knowledge_claims", ["release_id"]
    )

    op.create_table(
        "pet_knowledge_claim_sources",
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["pet_knowledge_claims.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["pet_knowledge_sources.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_knowledge_claim_sources"),
        sa.UniqueConstraint(
            "claim_id",
            "source_id",
            name="uq_pet_knowledge_claim_sources_claim_source",
        ),
    )
    op.create_index(
        "ix_pet_knowledge_claim_sources_claim_id",
        "pet_knowledge_claim_sources",
        ["claim_id"],
    )
    op.create_index(
        "ix_pet_knowledge_claim_sources_source_id",
        "pet_knowledge_claim_sources",
        ["source_id"],
    )


def downgrade() -> None:
    op.drop_table("pet_knowledge_claim_sources")
    op.drop_table("pet_knowledge_claims")
    op.drop_table("pet_knowledge_sources")
    op.drop_table("pet_knowledge_varieties")
    op.drop_table("pet_knowledge_breeds")
    op.drop_table("pet_knowledge_releases")
