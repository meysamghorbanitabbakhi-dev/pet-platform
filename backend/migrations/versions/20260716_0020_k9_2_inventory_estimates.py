"""K9.2 semantic inventory evidence and reorder snoozes.

Revision ID: 20260716_0020
Revises: 20260716_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260716_0020"
down_revision: str | None = "20260716_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("inventory_units", sa.Column("remaining_input_mode", sa.String(20)))
    op.add_column("inventory_units", sa.Column("remaining_low_grams", sa.Integer()))
    op.add_column("inventory_units", sa.Column("remaining_high_grams", sa.Integer()))
    op.add_column("inventory_units", sa.Column("remaining_provenance", JSONB()))
    op.add_column(
        "food_estimation_estimates",
        sa.Column("scope", sa.String(20), server_default="household", nullable=False),
    )
    op.add_column("food_estimation_estimates", sa.Column("pet_id", sa.Uuid()))
    op.add_column(
        "food_estimation_estimates", sa.Column("last_confirmed_at", sa.DateTime(timezone=True))
    )
    op.add_column("food_estimation_estimates", sa.Column("provenance", JSONB()))
    op.create_foreign_key(
        "estimate_pet", "food_estimation_estimates", "pets_pets", ["pet_id"], ["id"]
    )
    op.create_table(
        "inventory_reorder_snoozes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("inventory_unit_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("snoozed_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_low_days", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["inventory_unit_id"], ["inventory_units.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["household_id"], ["households_households.id"]),
        sa.ForeignKeyConstraint(["identity_id"], ["identity_auth_identities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inventory_unit_id", "identity_id", name="unit_identity"),
    )
    for column in ("inventory_unit_id", "household_id", "identity_id", "snoozed_until"):
        op.create_index(
            f"ix_inventory_reorder_snoozes_{column}", "inventory_reorder_snoozes", [column]
        )


def downgrade() -> None:
    op.drop_table("inventory_reorder_snoozes")
    op.drop_constraint("estimate_pet", "food_estimation_estimates", type_="foreignkey")
    for column in ("provenance", "last_confirmed_at", "pet_id", "scope"):
        op.drop_column("food_estimation_estimates", column)
    for column in (
        "remaining_provenance",
        "remaining_high_grams",
        "remaining_low_grams",
        "remaining_input_mode",
    ):
        op.drop_column("inventory_units", column)
