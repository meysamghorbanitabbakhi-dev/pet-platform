"""Pet health foundation.

Revision ID: 20260716_0009
Revises: 20260716_0008
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0009"
down_revision: str | None = "20260716_0008"
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
    op.add_column("pets_pets", sa.Column("birth_date_precision", sa.String(20)))
    op.add_column("pets_pets", sa.Column("sex", sa.String(20)))
    op.add_column("pets_pets", sa.Column("neuter_status", sa.String(20)))
    op.add_column("pets_pets", sa.Column("expected_adult_size", sa.String(20)))
    op.add_column("pets_pets", sa.Column("breed_reference_id", sa.String(150)))
    op.add_column("pets_pets", sa.Column("breed_variety_id", sa.String(150)))
    op.add_column("pets_pets", sa.Column("breed_identification_source", sa.String(40)))
    op.add_column(
        "pets_pets",
        sa.Column("mixed_breed", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("pets_pets", sa.Column("reproductive_state", sa.String(30)))
    op.create_index("ix_pets_pets_breed_reference_id", "pets_pets", ["breed_reference_id"])
    for name, condition in (
        (
            "valid_birth_date_precision",
            "birth_date_precision IS NULL OR birth_date_precision IN ('exact','month','year','estimated')",
        ),
        ("valid_sex", "sex IS NULL OR sex IN ('female','male','unknown')"),
        (
            "valid_neuter_status",
            "neuter_status IS NULL OR neuter_status IN ('intact','neutered','unknown')",
        ),
        (
            "valid_expected_adult_size",
            "expected_adult_size IS NULL OR expected_adult_size IN "
            "('very_small','small','medium','large','giant','unknown')",
        ),
        (
            "valid_breed_identification_source",
            "breed_identification_source IS NULL OR breed_identification_source IN "
            "('owner_reported','veterinarian_reported','registry_confirmed','dna_estimated','unknown')",
        ),
        (
            "valid_reproductive_state",
            "reproductive_state IS NULL OR reproductive_state IN "
            "('not_applicable','pregnant','lactating','unknown')",
        ),
    ):
        op.create_check_constraint(name, "pets_pets", condition)

    op.create_table(
        "pet_health_measurements",
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("measurement_type", sa.String(50), nullable=False),
        sa.Column("value", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("measurement_method", sa.String(100)),
        sa.Column("entered_by_identity_id", sa.Uuid(), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("supersedes_measurement_id", sa.Uuid()),
        sa.Column("correction_reason", sa.Text()),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "measurement_type IN ('weight','height_at_withers','chest_circumference',"
            "'body_length','temperature','resting_respiratory_rate')",
            name="ck_pet_health_measurements_valid_measurement_type",
        ),
        sa.CheckConstraint("value > 0", name="ck_pet_health_measurements_positive_value"),
        sa.CheckConstraint(
            "source IN ('owner_reported','veterinarian_reported','device_import')",
            name="ck_pet_health_measurements_valid_source",
        ),
        sa.CheckConstraint(
            "confidence IN ('low','medium','high')",
            name="ck_pet_health_measurements_valid_confidence",
        ),
        sa.CheckConstraint(
            "status IN ('active','corrected','voided')",
            name="ck_pet_health_measurements_valid_status",
        ),
        sa.ForeignKeyConstraint(["pet_id"], ["pets_pets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entered_by_identity_id"], ["identity_auth_identities.id"]),
        sa.ForeignKeyConstraint(
            ["supersedes_measurement_id"], ["pet_health_measurements.id"]
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pet_health_measurements"),
        sa.UniqueConstraint(
            "supersedes_measurement_id",
            name="uq_pet_health_measurements_supersedes_measurement_id",
        ),
    )
    op.create_index("ix_pet_health_measurements_pet_id", "pet_health_measurements", ["pet_id"])
    op.create_index(
        "ix_pet_health_measurements_entered_by_identity_id",
        "pet_health_measurements",
        ["entered_by_identity_id"],
    )

    op.create_table(
        "pet_health_measurement_reminders",
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("measurement_type", sa.String(50), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by_identity_id", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("dismissed_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "measurement_type IN ('weight','body_condition')",
            name="ck_pet_health_measurement_reminders_valid_measurement_type",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled','completed','dismissed')",
            name="ck_pet_health_measurement_reminders_valid_status",
        ),
        sa.ForeignKeyConstraint(["pet_id"], ["pets_pets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_identity_id"], ["identity_auth_identities.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_pet_health_measurement_reminders"),
    )
    op.create_index(
        "ix_pet_health_measurement_reminders_pet_id",
        "pet_health_measurement_reminders",
        ["pet_id"],
    )
    op.create_index(
        "ix_pet_health_measurement_reminders_due_at",
        "pet_health_measurement_reminders",
        ["due_at"],
    )


def downgrade() -> None:
    op.drop_table("pet_health_measurement_reminders")
    op.drop_table("pet_health_measurements")
    for name in (
        "valid_reproductive_state",
        "valid_breed_identification_source",
        "valid_expected_adult_size",
        "valid_neuter_status",
        "valid_sex",
        "valid_birth_date_precision",
    ):
        op.drop_constraint(f"ck_pets_pets_{name}", "pets_pets", type_="check")
    op.drop_index("ix_pets_pets_breed_reference_id", table_name="pets_pets")
    for column in (
        "reproductive_state",
        "mixed_breed",
        "breed_identification_source",
        "breed_variety_id",
        "breed_reference_id",
        "expected_adult_size",
        "neuter_status",
        "sex",
        "birth_date_precision",
    ):
        op.drop_column("pets_pets", column)
