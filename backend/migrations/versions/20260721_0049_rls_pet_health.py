"""Protect pet health records via pet_id -> pets_pets (Workstream 9 continuation).

Revision ID: 20260721_0049
Revises: 20260721_0048

Sensitive pet health/medical data with no household_id of its own:
pet_health_measurements, pet_health_measurement_reminders,
pet_health_consents, pet_health_assets (photos/medical documents),
pet_health_body_assessments all carry pet_id directly (pets_pets is
already household-scoped); pet_health_body_assessment_assets reaches it
via assessment_id -> pet_health_body_assessments.pet_id (two hops).

pet_health_benchmark_definitions is deliberately excluded: it has no
pet_id at all -- it is knowledge-base reference data (breed/population
growth benchmarks sourced from pet_knowledge_claims), not a per-pet
row, matching pet_knowledge_*'s existing exclusion.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260721_0049"
down_revision: str | None = "20260721_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PET_ID_TABLES = (
    "pet_health_measurements",
    "pet_health_measurement_reminders",
    "pet_health_consents",
    "pet_health_assets",
    "pet_health_body_assessments",
)


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

    op.execute("ALTER TABLE pet_health_body_assessment_assets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE pet_health_body_assessment_assets FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY pet_health_body_assessment_assets_isolation "
        "ON pet_health_body_assessment_assets "
        "USING (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM pet_health_body_assessments a JOIN pets_pets p ON p.id = a.pet_id"
        "  WHERE a.id = pet_health_body_assessment_assets.assessment_id"
        "   AND p.household_id = ANY(app_household_ids())"
        ")) "
        "WITH CHECK (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM pet_health_body_assessments a JOIN pets_pets p ON p.id = a.pet_id"
        "  WHERE a.id = pet_health_body_assessment_assets.assessment_id"
        "   AND p.household_id = ANY(app_household_ids())"
        "))"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS pet_health_body_assessment_assets_isolation "
        "ON pet_health_body_assessment_assets"
    )
    op.execute("ALTER TABLE pet_health_body_assessment_assets DISABLE ROW LEVEL SECURITY")

    for table in _PET_ID_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
