"""Pet life foundation.

Revision ID: 20260716_0003
Revises: 20260716_0002
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0003"
down_revision: str | None = "20260716_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[object]]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "households_households",
        sa.Column("name", sa.String(200), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_households_households"),
    )
    op.create_table(
        "households_memberships",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_households.id"],
            ondelete="CASCADE",
            name="fk_households_memberships_household_id_households_households",
        ),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identity_auth_identities.id"],
            ondelete="CASCADE",
            name="fk_households_memberships_identity_id_identity_auth_identities",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_households_memberships"),
        sa.UniqueConstraint("household_id", "identity_id", name="uq_households_memberships_member"),
    )
    op.create_index(
        "ix_households_memberships_household_id", "households_memberships", ["household_id"]
    )
    op.create_index(
        "ix_households_memberships_identity_id", "households_memberships", ["identity_id"]
    )
    op.create_table(
        "pets_pets",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("species", sa.String(20), nullable=False),
        sa.Column("birth_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("species IN ('dog','cat')", name="ck_pets_pets_valid_species"),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_pets_pets_valid_status"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_households.id"],
            ondelete="CASCADE",
            name="fk_pets_pets_household_id_households_households",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pets_pets"),
    )
    op.create_index("ix_pets_pets_household_id", "pets_pets", ["household_id"])
    op.create_table(
        "inventory_units",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("order_line_id", sa.Uuid()),
        sa.Column("product_id", sa.Uuid()),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("initial_quantity_grams", sa.Integer()),
        sa.Column("remaining_quantity_grams", sa.Integer()),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "source IN ('platform_order','external_purchase')",
            name="ck_inventory_units_valid_source",
        ),
        sa.CheckConstraint(
            "state IN ('unopened','opened','exhausted','discarded')",
            name="ck_inventory_units_valid_state",
        ),
        sa.CheckConstraint(
            "initial_quantity_grams IS NULL OR initial_quantity_grams > 0",
            name="ck_inventory_units_positive_initial_quantity",
        ),
        sa.CheckConstraint(
            "remaining_quantity_grams IS NULL OR remaining_quantity_grams >= 0",
            name="ck_inventory_units_nonnegative_remaining_quantity",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_households.id"],
            name="fk_inventory_units_household_id_households_households",
        ),
        sa.ForeignKeyConstraint(
            ["order_line_id"],
            ["orders_order_lines.id"],
            name="fk_inventory_units_order_line_id_orders_order_lines",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["catalog_products.id"],
            name="fk_inventory_units_product_id_catalog_products",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_units"),
        sa.UniqueConstraint("order_line_id", name="uq_inventory_units_order_line_id"),
    )
    op.create_index("ix_inventory_units_household_id", "inventory_units", ["household_id"])
    op.create_index("ix_inventory_units_product_id", "inventory_units", ["product_id"])
    op.create_table(
        "inventory_consumption_assignments",
        sa.Column("inventory_unit_id", sa.Uuid(), nullable=False),
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("share_basis_points", sa.Integer()),
        sa.Column("daily_portion_grams", sa.Integer()),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "share_basis_points IS NULL OR (share_basis_points > 0 AND share_basis_points <= 10000)",
            name="ck_inventory_consumption_assignments_valid_share",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_unit_id"],
            ["inventory_units.id"],
            ondelete="CASCADE",
            name="fk_consumption_assignments_inventory_unit_id",
        ),
        sa.ForeignKeyConstraint(
            ["pet_id"],
            ["pets_pets.id"],
            ondelete="CASCADE",
            name="fk_inventory_consumption_assignments_pet_id_pets_pets",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_consumption_assignments"),
        sa.UniqueConstraint(
            "inventory_unit_id", "pet_id", name="uq_inventory_consumption_assignments_unit_pet"
        ),
    )
    op.create_index(
        "ix_inventory_consumption_assignments_inventory_unit_id",
        "inventory_consumption_assignments",
        ["inventory_unit_id"],
    )
    op.create_index(
        "ix_inventory_consumption_assignments_pet_id",
        "inventory_consumption_assignments",
        ["pet_id"],
    )
    op.create_table(
        "food_estimation_estimates",
        sa.Column("inventory_unit_id", sa.Uuid(), nullable=False),
        sa.Column("low_days", sa.Integer()),
        sa.Column("high_days", sa.Integer()),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("basis", sa.String(50), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(low_days IS NULL AND high_days IS NULL) OR (low_days >= 0 AND high_days >= low_days)",
            name="ck_food_estimation_estimates_valid_range",
        ),
        sa.CheckConstraint(
            "confidence IN ('low','medium','high')",
            name="ck_food_estimation_estimates_valid_confidence",
        ),
        sa.CheckConstraint(
            "status IN ('active','corrected','exhausted')",
            name="ck_food_estimation_estimates_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_unit_id"],
            ["inventory_units.id"],
            name="fk_food_estimation_estimates_inventory_unit_id_inventory_units",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_food_estimation_estimates"),
    )
    op.create_index(
        "ix_food_estimation_estimates_inventory_unit_id",
        "food_estimation_estimates",
        ["inventory_unit_id"],
    )
    op.create_table(
        "journeys_definitions",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title_fa", sa.String(300), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("approval_status", sa.String(20), nullable=False),
        sa.Column("approved_by", sa.String(200)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "approval_status IN ('draft','approved','retired')",
            name="ck_journeys_definitions_valid_approval_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_journeys_definitions"),
        sa.UniqueConstraint("key", "version", name="uq_journeys_definitions_key_version"),
    )
    op.create_table(
        "journeys_pet_journeys",
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("stop_reason", sa.Text()),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('active','paused','stopped','completed')",
            name="ck_journeys_pet_journeys_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["journeys_definitions.id"],
            name="fk_journeys_pet_journeys_definition_id_journeys_definitions",
        ),
        sa.ForeignKeyConstraint(
            ["pet_id"],
            ["pets_pets.id"],
            ondelete="CASCADE",
            name="fk_journeys_pet_journeys_pet_id_pets_pets",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_journeys_pet_journeys"),
    )
    op.create_index(
        "ix_journeys_pet_journeys_definition_id", "journeys_pet_journeys", ["definition_id"]
    )
    op.create_index("ix_journeys_pet_journeys_pet_id", "journeys_pet_journeys", ["pet_id"])
    op.create_table(
        "diary_entries",
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("entry_type", sa.String(50), nullable=False),
        sa.Column("title_fa", sa.String(300), nullable=False),
        sa.Column("note_fa", sa.Text()),
        sa.Column("happened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pet_id"],
            ["pets_pets.id"],
            ondelete="CASCADE",
            name="fk_diary_entries_pet_id_pets_pets",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_diary_entries"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_diary_entries_source_once"),
    )
    op.create_index("ix_diary_entries_pet_id", "diary_entries", ["pet_id"])
    op.create_table(
        "garden_rewards",
        sa.Column("pet_id", sa.Uuid(), nullable=False),
        sa.Column("diary_entry_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("object_key", sa.String(100), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("quadrant", sa.Integer()),
        sa.Column("position_x", sa.Integer()),
        sa.Column("position_y", sa.Integer()),
        sa.Column("placed_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "state IN ('revealed','placed','stored')", name="ck_garden_rewards_valid_state"
        ),
        sa.CheckConstraint(
            "source_type IN ('journey_completion','owner_milestone','profile_enrichment','durable_memory')",
            name="ck_garden_rewards_eligible_source",
        ),
        sa.ForeignKeyConstraint(
            ["diary_entry_id"],
            ["diary_entries.id"],
            name="fk_garden_rewards_diary_entry_id_diary_entries",
        ),
        sa.ForeignKeyConstraint(
            ["pet_id"],
            ["pets_pets.id"],
            ondelete="CASCADE",
            name="fk_garden_rewards_pet_id_pets_pets",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_garden_rewards"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_garden_rewards_source_once"),
    )
    op.create_index("ix_garden_rewards_pet_id", "garden_rewards", ["pet_id"])


def downgrade() -> None:
    op.drop_index("ix_garden_rewards_pet_id", table_name="garden_rewards")
    op.drop_table("garden_rewards")
    op.drop_index("ix_diary_entries_pet_id", table_name="diary_entries")
    op.drop_table("diary_entries")
    op.drop_index("ix_journeys_pet_journeys_pet_id", table_name="journeys_pet_journeys")
    op.drop_index("ix_journeys_pet_journeys_definition_id", table_name="journeys_pet_journeys")
    op.drop_table("journeys_pet_journeys")
    op.drop_table("journeys_definitions")
    op.drop_index(
        "ix_food_estimation_estimates_inventory_unit_id", table_name="food_estimation_estimates"
    )
    op.drop_table("food_estimation_estimates")
    op.drop_index(
        "ix_inventory_consumption_assignments_pet_id",
        table_name="inventory_consumption_assignments",
    )
    op.drop_index(
        "ix_inventory_consumption_assignments_inventory_unit_id",
        table_name="inventory_consumption_assignments",
    )
    op.drop_table("inventory_consumption_assignments")
    op.drop_index("ix_inventory_units_product_id", table_name="inventory_units")
    op.drop_index("ix_inventory_units_household_id", table_name="inventory_units")
    op.drop_table("inventory_units")
    op.drop_index("ix_pets_pets_household_id", table_name="pets_pets")
    op.drop_table("pets_pets")
    op.drop_index("ix_households_memberships_identity_id", table_name="households_memberships")
    op.drop_index("ix_households_memberships_household_id", table_name="households_memberships")
    op.drop_table("households_memberships")
    op.drop_table("households_households")
