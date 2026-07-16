"""Private pet assets, consent, and body assessments.

Revision ID: 20260716_0010
Revises: 20260716_0009
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0010"
down_revision: str | None = "20260716_0009"
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
        "pet_health_consents",
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("granted_by_identity_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("policy_version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('body_photographs','medical_records')",
            name="ck_pet_health_consents_valid_purpose",
        ),
        sa.CheckConstraint(
            "status IN ('granted','withdrawn')",
            name="ck_pet_health_consents_valid_status",
        ),
        sa.ForeignKeyConstraint(["pet_id"], ["pets_pets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_identity_id"], ["identity_auth_identities.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_pet_health_consents"),
    )
    op.create_index("ix_pet_health_consents_pet_id", "pet_health_consents", ["pet_id"])
    op.create_index(
        "ix_pet_health_consents_granted_by_identity_id",
        "pet_health_consents",
        ["granted_by_identity_id"],
    )
    op.create_index(
        "uq_pet_health_consents_active_purpose",
        "pet_health_consents",
        ["pet_id", "purpose"],
        unique=True,
        postgresql_where=sa.text("status = 'granted'"),
    )

    op.create_table(
        "pet_health_assets",
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("consent_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_identity_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("original_filename", sa.String(300), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "category IN "
            "('body_top','body_side','medical_document','lab_result','other_medical')",
            name="ck_pet_health_assets_valid_category",
        ),
        sa.CheckConstraint(
            "purpose IN ('body_photographs','medical_records')",
            name="ck_pet_health_assets_valid_purpose",
        ),
        sa.CheckConstraint(
            "status IN ('active','removed')", name="ck_pet_health_assets_valid_status"
        ),
        sa.ForeignKeyConstraint(["pet_id"], ["pets_pets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["consent_id"], ["pet_health_consents.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_identity_id"], ["identity_auth_identities.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_pet_health_assets"),
        sa.UniqueConstraint("storage_key", name="uq_pet_health_assets_storage_key"),
    )
    op.create_index("ix_pet_health_assets_pet_id", "pet_health_assets", ["pet_id"])
    op.create_index("ix_pet_health_assets_consent_id", "pet_health_assets", ["consent_id"])
    op.create_index(
        "ix_pet_health_assets_uploaded_by_identity_id",
        "pet_health_assets",
        ["uploaded_by_identity_id"],
    )

    op.create_table(
        "pet_health_body_assessments",
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("bcs_score", sa.Integer(), nullable=False),
        sa.Column("bcs_scale", sa.Integer(), nullable=False),
        sa.Column("muscle_condition", sa.String(30), nullable=False),
        sa.Column("assessment_source", sa.String(40), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entered_by_identity_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("veterinarian_name", sa.String(200)),
        sa.Column("veterinarian_credential", sa.String(200)),
        sa.Column("confirmed_by_operator_id", sa.Uuid()),
        sa.Column("veterinarian_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmation_evidence_file_id", sa.Uuid()),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "bcs_score >= 1 AND bcs_score <= 9",
            name="ck_pet_health_body_assessments_valid_bcs_score",
        ),
        sa.CheckConstraint(
            "bcs_scale = 9", name="ck_pet_health_body_assessments_valid_bcs_scale"
        ),
        sa.CheckConstraint(
            "muscle_condition IN "
            "('normal','mild_loss','moderate_loss','severe_loss','unknown')",
            name="ck_pet_health_body_assessments_valid_muscle_condition",
        ),
        sa.CheckConstraint(
            "assessment_source IN ('owner_reported','veterinarian_confirmed')",
            name="ck_pet_health_body_assessments_valid_assessment_source",
        ),
        sa.CheckConstraint(
            "status IN ('active','superseded','voided')",
            name="ck_pet_health_body_assessments_valid_status",
        ),
        sa.ForeignKeyConstraint(["pet_id"], ["pets_pets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entered_by_identity_id"], ["identity_auth_identities.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_operator_id"], ["identity_auth_identities.id"]),
        sa.ForeignKeyConstraint(
            ["confirmation_evidence_file_id"], ["trust_evidence_files.id"]
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_health_body_assessments"),
    )
    op.create_index(
        "ix_pet_health_body_assessments_pet_id",
        "pet_health_body_assessments",
        ["pet_id"],
    )
    op.create_index(
        "ix_pet_health_body_assessments_entered_by_identity_id",
        "pet_health_body_assessments",
        ["entered_by_identity_id"],
    )

    op.create_table(
        "pet_health_body_assessment_assets",
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "role IN ('top','side','supporting')",
            name="ck_pet_health_body_assessment_assets_valid_role",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["pet_health_body_assessments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["pet_health_assets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_health_body_assessment_assets"),
        sa.UniqueConstraint(
            "assessment_id",
            "asset_id",
            name="uq_pet_health_body_assessment_assets_assessment_asset",
        ),
    )
    op.create_index(
        "ix_pet_health_body_assessment_assets_assessment_id",
        "pet_health_body_assessment_assets",
        ["assessment_id"],
    )
    op.create_index(
        "ix_pet_health_body_assessment_assets_asset_id",
        "pet_health_body_assessment_assets",
        ["asset_id"],
    )


def downgrade() -> None:
    op.drop_table("pet_health_body_assessment_assets")
    op.drop_table("pet_health_body_assessments")
    op.drop_table("pet_health_assets")
    op.drop_table("pet_health_consents")
