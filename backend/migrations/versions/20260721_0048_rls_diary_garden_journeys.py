"""Protect diary, garden, and pet-journey tables via pet_id -> pets_pets (Workstream 9 continuation).

Revision ID: 20260721_0048
Revises: 20260721_0047

Continues the tenant-owned-child-table sweep: diary_entries,
garden_rewards, and journeys_pet_journeys all carry pet_id directly
(pets_pets is already household-scoped); journey_check_ins has no
pet_id of its own but reaches it via journey_id ->
journeys_pet_journeys.pet_id (two hops), the same shape as this
program's other two-hop child-table policies.

journeys_definitions is deliberately excluded: it is catalog-like
reference data (the approved journey templates every household can
start, not a per-household or per-pet row), matching how
pet_knowledge_*/catalog_products are already out of RLS scope for the
same reason.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260721_0048"
down_revision: str | None = "20260721_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PET_ID_TABLES = ("diary_entries", "garden_rewards", "journeys_pet_journeys")


def upgrade() -> None:
    for table in _PET_ID_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_isolation ON {table} "
            "USING (app_is_operator() OR EXISTS ("
            f"  SELECT 1 FROM pets_pets p WHERE p.id = {table}.pet_id"
            "   AND p.household_id = ANY(app_household_ids())"
            ")) "
            "WITH CHECK (app_is_operator() OR EXISTS ("
            f"  SELECT 1 FROM pets_pets p WHERE p.id = {table}.pet_id"
            "   AND p.household_id = ANY(app_household_ids())"
            "))"
        )

    op.execute("ALTER TABLE journey_check_ins ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE journey_check_ins FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY journey_check_ins_isolation ON journey_check_ins "
        "USING (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM journeys_pet_journeys pj JOIN pets_pets p ON p.id = pj.pet_id"
        "  WHERE pj.id = journey_check_ins.journey_id"
        "   AND p.household_id = ANY(app_household_ids())"
        ")) "
        "WITH CHECK (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM journeys_pet_journeys pj JOIN pets_pets p ON p.id = pj.pet_id"
        "  WHERE pj.id = journey_check_ins.journey_id"
        "   AND p.household_id = ANY(app_household_ids())"
        "))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS journey_check_ins_isolation ON journey_check_ins")
    op.execute("ALTER TABLE journey_check_ins DISABLE ROW LEVEL SECURITY")

    for table in _PET_ID_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
