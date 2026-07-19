"""Validated breed selection history.

Revision ID: 20260716_0017
Revises: 20260716_0016
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0017"
down_revision: str | None = "20260716_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pets_pets", sa.Column("breed_selection_mode", sa.String(20)))
    op.create_check_constraint(
        "valid_breed_selection_mode",
        "pets_pets",
        "breed_selection_mode IS NULL OR breed_selection_mode IN ('known','mixed','unknown')",
    )
    op.create_table(
        "pets_breed_selections",
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_release_id", sa.Uuid(), nullable=False),
        sa.Column("selection_mode", sa.String(20), nullable=False),
        sa.Column("breed_reference_id", sa.String(150)),
        sa.Column("breed_variety_id", sa.String(150)),
        sa.Column("identification_source", sa.String(40), nullable=False),
        sa.Column("selected_by_identity_id", sa.Uuid(), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "selection_mode IN ('known','mixed','unknown')",
            name="ck_pets_breed_selections_valid_mode",
        ),
        sa.CheckConstraint(
            "identification_source IN ('owner_reported','veterinarian_reported',"
            "'registry_confirmed','dna_estimated','unknown')",
            name="ck_pets_breed_selections_valid_identification_source",
        ),
        sa.CheckConstraint(
            "(selection_mode = 'known' AND breed_reference_id IS NOT NULL) OR "
            "(selection_mode IN ('mixed','unknown') AND breed_reference_id IS NULL)",
            name="ck_pets_breed_selections_valid_selection_target",
        ),
        sa.ForeignKeyConstraint(["pet_id"], ["pets_pets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["knowledge_release_id"], ["pet_knowledge_releases.id"]
        ),
        sa.ForeignKeyConstraint(
            ["selected_by_identity_id"], ["identity_auth_identities.id"]
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pets_breed_selections"),
    )
    for column in ("pet_id", "knowledge_release_id", "selected_by_identity_id"):
        op.create_index(
            f"ix_pets_breed_selections_{column}", "pets_breed_selections", [column]
        )


def downgrade() -> None:
    op.drop_table("pets_breed_selections")
    op.drop_constraint(
        "ck_pets_pets_valid_breed_selection_mode", "pets_pets", type_="check"
    )
    op.drop_column("pets_pets", "breed_selection_mode")
