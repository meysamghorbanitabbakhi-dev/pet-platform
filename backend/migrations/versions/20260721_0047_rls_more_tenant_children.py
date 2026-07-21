"""Protect more tenant-owned child tables named in the gap-closure brief (Workstream 9 continuation).

Revision ID: 20260721_0047
Revises: 20260721_0046

20260720_0041 explicitly deferred every child table with no
household_id/customer_identity_id column of its own, "each needs its
own considered EXISTS-based policy against its parent, verified
individually." 20260720_0044 closed the highest-severity subset (order
lines, payment attempts, shelf-life exceptions, wallet ledger,
households_addresses). This migration covers the remaining tables
named directly in the brief's own list -- "delivery estimates" (order
fulfillment/delay/resolution records) and "pet/breed/assignment
children" (food estimates, consumption assignments, breed selections):

- food_estimation_estimates: via inventory_unit_id -> inventory_units,
  already household-scoped.
- inventory_consumption_assignments: same, via inventory_unit_id.
- pets_breed_selections: via pet_id -> pets_pets, already
  household-scoped.
- orders_fulfillment_events, orders_resolutions: via order_id ->
  orders_orders, already customer_identity_id-scoped.
- orders_delay_acknowledgements: this table already carries identity_id
  directly (the acknowledging customer) -- used directly rather than
  joining through order_id, since that is the table's actual ownership
  column (matches how customer_order_journey and related routes read
  it), not an incidental duplicate of orders_orders' own scoping.
- orders_order_line_pet_plans: via order_line_id -> orders_order_lines
  -> orders_orders (two hops), mirroring 20260720_0044's identical
  pattern for orders_shelf_life_exceptions.

Other child tables (pet_health_*, journeys_*, diary_entries,
garden_rewards, notifications_*, concierge_offer_events,
replenishment_reservation_events, reservations_events,
support_customer_request_status_audit) remain explicit, named
follow-up -- not silently skipped, recorded in the gap-closure
handover -- for the same reason 20260720_0041 gave: verifying ~15 more
tables' actual customer-facing read paths individually in one pass
trades a low-risk, well-tested core for a rushed, unverified one.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260721_0047"
down_revision: str | None = "20260721_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- food_estimation_estimates / inventory_consumption_assignments:
    # via inventory_unit_id -> inventory_units.household_id ---
    for table in ("food_estimation_estimates", "inventory_consumption_assignments"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_isolation ON {table} "
            "USING (app_is_operator() OR EXISTS ("
            f"  SELECT 1 FROM inventory_units iu WHERE iu.id = {table}.inventory_unit_id"
            "   AND iu.household_id = ANY(app_household_ids())"
            ")) "
            "WITH CHECK (app_is_operator() OR EXISTS ("
            f"  SELECT 1 FROM inventory_units iu WHERE iu.id = {table}.inventory_unit_id"
            "   AND iu.household_id = ANY(app_household_ids())"
            "))"
        )

    # --- pets_breed_selections: via pet_id -> pets_pets.household_id ---
    op.execute("ALTER TABLE pets_breed_selections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE pets_breed_selections FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY pets_breed_selections_isolation ON pets_breed_selections "
        "USING (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM pets_pets p WHERE p.id = pets_breed_selections.pet_id"
        "   AND p.household_id = ANY(app_household_ids())"
        ")) "
        "WITH CHECK (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM pets_pets p WHERE p.id = pets_breed_selections.pet_id"
        "   AND p.household_id = ANY(app_household_ids())"
        "))"
    )

    # --- orders_fulfillment_events / orders_resolutions: via order_id ->
    # orders_orders.customer_identity_id ---
    for table in ("orders_fulfillment_events", "orders_resolutions"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_isolation ON {table} "
            "USING (app_is_operator() OR EXISTS ("
            f"  SELECT 1 FROM orders_orders o WHERE o.id = {table}.order_id"
            "   AND o.customer_identity_id = app_identity_id()"
            ")) "
            "WITH CHECK (app_is_operator() OR EXISTS ("
            f"  SELECT 1 FROM orders_orders o WHERE o.id = {table}.order_id"
            "   AND o.customer_identity_id = app_identity_id()"
            "))"
        )

    # --- orders_delay_acknowledgements: identity_id is this table's own
    # ownership column ---
    op.execute("ALTER TABLE orders_delay_acknowledgements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE orders_delay_acknowledgements FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY orders_delay_acknowledgements_isolation ON orders_delay_acknowledgements "
        "USING (app_is_operator() OR identity_id = app_identity_id()) "
        "WITH CHECK (app_is_operator() OR identity_id = app_identity_id())"
    )

    # --- orders_order_line_pet_plans: via order_line_id -> orders_order_lines
    # -> orders_orders.customer_identity_id (two hops) ---
    op.execute("ALTER TABLE orders_order_line_pet_plans ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE orders_order_line_pet_plans FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY orders_order_line_pet_plans_isolation ON orders_order_line_pet_plans "
        "USING (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM orders_order_lines ol JOIN orders_orders o ON o.id = ol.order_id"
        "  WHERE ol.id = orders_order_line_pet_plans.order_line_id"
        "   AND o.customer_identity_id = app_identity_id()"
        ")) "
        "WITH CHECK (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM orders_order_lines ol JOIN orders_orders o ON o.id = ol.order_id"
        "  WHERE ol.id = orders_order_line_pet_plans.order_line_id"
        "   AND o.customer_identity_id = app_identity_id()"
        "))"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS orders_order_line_pet_plans_isolation ON orders_order_line_pet_plans"
    )
    op.execute("ALTER TABLE orders_order_line_pet_plans DISABLE ROW LEVEL SECURITY")

    op.execute(
        "DROP POLICY IF EXISTS orders_delay_acknowledgements_isolation "
        "ON orders_delay_acknowledgements"
    )
    op.execute("ALTER TABLE orders_delay_acknowledgements DISABLE ROW LEVEL SECURITY")

    for table in ("orders_fulfillment_events", "orders_resolutions"):
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS pets_breed_selections_isolation ON pets_breed_selections")
    op.execute("ALTER TABLE pets_breed_selections DISABLE ROW LEVEL SECURITY")

    for table in ("food_estimation_estimates", "inventory_consumption_assignments"):
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
