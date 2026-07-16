"""Provenance-aware pet reference benchmarks.

Revision ID: 20260716_0014
Revises: 20260716_0013
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0014"
down_revision: str | None = "20260716_0013"
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
        "pet_health_benchmark_definitions",
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("breed_external_id", sa.String(150), nullable=False),
        sa.Column("variety_external_id", sa.String(150)),
        sa.Column("measurement_type", sa.String(50), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("reference_purpose", sa.String(40), nullable=False),
        sa.Column("minimum_value", sa.Numeric(12, 3), nullable=False),
        sa.Column("maximum_value", sa.Numeric(12, 3), nullable=False),
        sa.Column("minimum_age_days", sa.Integer()),
        sa.Column("maximum_age_days", sa.Integer()),
        sa.Column("life_stage", sa.String(40)),
        sa.Column("sex_scope", sa.String(20), nullable=False),
        sa.Column("neuter_scope", sa.String(20), nullable=False),
        sa.Column("population_geography", sa.String(200), nullable=False),
        sa.Column("measurement_definition_fa", sa.Text(), nullable=False),
        sa.Column("comparison_allowed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("recorded_by_operator_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "measurement_type IN ('weight','height_at_withers')",
            name="ck_pet_health_benchmark_definitions_valid_measurement_type",
        ),
        sa.CheckConstraint(
            "unit IN ('kg','cm')", name="ck_pet_health_benchmark_definitions_valid_unit"
        ),
        sa.CheckConstraint(
            "(measurement_type = 'weight' AND unit = 'kg') OR "
            "(measurement_type = 'height_at_withers' AND unit = 'cm')",
            name="ck_pet_health_benchmark_definitions_measurement_unit_match",
        ),
        sa.CheckConstraint(
            "reference_purpose IN ('registry_conformation','population_reference',"
            "'growth_reference')",
            name="ck_pet_health_benchmark_definitions_valid_reference_purpose",
        ),
        sa.CheckConstraint(
            "minimum_value >= 0 AND maximum_value >= minimum_value",
            name="ck_pet_health_benchmark_definitions_valid_range",
        ),
        sa.CheckConstraint(
            "minimum_age_days IS NULL OR maximum_age_days IS NULL OR "
            "maximum_age_days >= minimum_age_days",
            name="ck_pet_health_benchmark_definitions_valid_age_range",
        ),
        sa.CheckConstraint(
            "sex_scope IN ('combined','female','male')",
            name="ck_pet_health_benchmark_definitions_valid_sex_scope",
        ),
        sa.CheckConstraint(
            "neuter_scope IN ('any','intact','neutered')",
            name="ck_pet_health_benchmark_definitions_valid_neuter_scope",
        ),
        sa.CheckConstraint(
            "status IN ('active','withdrawn')",
            name="ck_pet_health_benchmark_definitions_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"], ["pet_knowledge_releases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["pet_knowledge_claims.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_operator_id"], ["identity_auth_identities.id"]
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_health_benchmark_definitions"),
        sa.UniqueConstraint(
            "claim_id", name="uq_pet_health_benchmark_definitions_one_definition_per_claim"
        ),
    )
    for column in ("release_id", "claim_id", "breed_external_id", "recorded_by_operator_id"):
        op.create_index(
            f"ix_pet_health_benchmark_definitions_{column}",
            "pet_health_benchmark_definitions",
            [column],
        )


def downgrade() -> None:
    op.drop_table("pet_health_benchmark_definitions")
