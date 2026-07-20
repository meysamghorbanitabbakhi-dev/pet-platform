"""Restrict household self-enrollment, protect addresses/order/payment/wallet children (Workstream 9 continuation).

Revision ID: 20260720_0044
Revises: 20260720_0043

Two real defects found auditing 20260720_0041/0042's actual policies
against exactly the scenarios they were meant to prevent, not assumed:

1. households_memberships_insert's bootstrap fallback
   (`identity_id = app_identity_id()`) lets ANY authenticated identity
   insert a membership row for themselves into ANY household_id, with no
   relationship to that household required at all -- not just the
   "I just created this household" case it exists for. No current route
   exploits this (create_household is the only membership-INSERT caller,
   and it only ever targets a household it just created), but this
   policy is the real, defense-in-depth security boundary Workstream 9
   exists to provide -- "no current app bug happens to reach it" is not
   the same as it being safe. Narrowed to: self-insertion is only allowed
   when (a) this identity is that specific household's
   created_by_identity_id, AND (b) no membership row exists yet for that
   household at all -- true first-membership bootstrap only. Condition
   (b) also closes the "creator revoked, re-enrolls later" gap: once any
   membership exists (or ever existed and persists as at least one row),
   the fallback stops applying to a creator who is not currently a
   member, regardless of how long ago they created the household.

2. households_households' created_by_identity_id fallback (added in
   20260720_0042 to solve a real Postgres RLS RETURNING-vs-SELECT-policy
   timing problem at INSERT) was copied verbatim onto UPDATE and DELETE
   too. Checked every route touching households_households: none
   performs an UPDATE or DELETE today, so that copy serves no current
   purpose -- and Postgres only evaluates INSERT/UPDATE ... RETURNING
   against the table's SELECT policy, never its UPDATE/DELETE policies,
   so the original RETURNING problem never needed an UPDATE/DELETE
   fallback in the first place. Left in place, it would grant a
   household's creator standing UPDATE/DELETE access forever, with no
   revocation possible, the moment such a route is ever added -- dropped
   entirely rather than carried forward as unexamined dead permission.
   The SELECT fallback keeps the same bootstrap-only scoping added to
   households_memberships above (only while no membership row exists
   yet for that household), so it no longer grants a former creator
   permanent standing read access either.

3. households_households_insert was `WITH CHECK (true)` -- unconditional.
   Tightened to require the inserted row's created_by_identity_id match
   the requester (or an operator), so the app-role connection cannot
   insert a household attributed to a different identity than the one
   making the request.

The first draft of fixes 1-2 used a plain correlated `NOT EXISTS (SELECT
1 FROM households_memberships ...)` inside these policies -- caught by
this migration's own paired adversarial tests, not assumed correct: a
policy's own subquery against an RLS-protected table is itself filtered
by that table's SELECT policy for the CURRENT calling identity, so
"does household X have any member" silently read as "does household X
have any member *that I am already allowed to see*" -- true for a
brand-new household (nothing to hide yet, the genuine bootstrap case)
but ALSO true for an abandoned household with real *other* members the
checking identity simply isn't allowed to see, defeating the very guard
meant to stop that case. Fixed with two `SECURITY DEFINER` helper
functions (app_household_creator / app_household_has_any_membership):
owned by the migration-running (superuser) role, so they see the true
global state, exactly the standard Postgres pattern for a policy that
needs to check a fact the calling role's own row security would
otherwise hide from it. `SET search_path = public` on both closes the
standard SECURITY DEFINER search-path-injection risk.

Also brings households_addresses and the tenant-owned child tables
named directly in this program's brief (order lines, payment attempts,
shelf-life exceptions, wallet ledger) under RLS via secure EXISTS
policies against their already-protected parent -- these have no
household_id/customer_identity_id column of their own, so 20260720_0041
explicitly deferred them ("each needs its own considered EXISTS-based
policy against its parent, verified individually"). This migration does
that for the tables named in the brief; other child tables without a
customer-facing read path of their own remain explicit follow-up (not
silently skipped -- recorded in the paired handover doc), consistent
with 20260720_0041's own stated reason for not bundling ~15 more tables
into one unverified pass.

Downgrade restores the exact prior policy text; lossless (no data
changes here, only policy definitions).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260720_0044"
down_revision: str | None = "20260720_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHILD_TABLES_VIA_ORDER = ("orders_order_lines", "payments_attempts")

_HELPER_FUNCTIONS_SQL = """
CREATE FUNCTION app_household_creator(p_household_id uuid) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT created_by_identity_id FROM households_households WHERE id = p_household_id
$$
"""

_HAS_ANY_MEMBERSHIP_FUNCTION_SQL = """
CREATE FUNCTION app_household_has_any_membership(p_household_id uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (SELECT 1 FROM households_memberships WHERE household_id = p_household_id)
$$
"""


def upgrade() -> None:
    op.execute(_HELPER_FUNCTIONS_SQL)
    op.execute(_HAS_ANY_MEMBERSHIP_FUNCTION_SQL)

    # --- households_households: restrict INSERT, scope SELECT bootstrap
    # fallback, drop the never-used UPDATE/DELETE creator fallback ---
    op.execute("DROP POLICY households_households_insert ON households_households")
    op.execute(
        "CREATE POLICY households_households_insert ON households_households "
        "FOR INSERT WITH CHECK (app_is_operator() OR created_by_identity_id = app_identity_id())"
    )

    op.execute("DROP POLICY households_households_select ON households_households")
    op.execute(
        "CREATE POLICY households_households_select ON households_households "
        "FOR SELECT USING ("
        "  app_is_operator()"
        "  OR id = ANY(app_household_ids())"
        "  OR ("
        "    created_by_identity_id = app_identity_id()"
        "    AND NOT app_household_has_any_membership(id)"
        "  )"
        ")"
    )

    op.execute("DROP POLICY households_households_update ON households_households")
    op.execute(
        "CREATE POLICY households_households_update ON households_households "
        "FOR UPDATE USING (app_is_operator() OR id = ANY(app_household_ids())) "
        "WITH CHECK (app_is_operator() OR id = ANY(app_household_ids()))"
    )

    op.execute("DROP POLICY households_households_delete ON households_households")
    op.execute(
        "CREATE POLICY households_households_delete ON households_households "
        "FOR DELETE USING (app_is_operator() OR id = ANY(app_household_ids()))"
    )

    # --- households_memberships: scope the self-enrollment INSERT
    # fallback to "creator of that exact household, and no membership
    # row exists yet" -- true bootstrap only, not arbitrary self-enroll. ---
    op.execute("DROP POLICY households_memberships_insert ON households_memberships")
    op.execute(
        "CREATE POLICY households_memberships_insert ON households_memberships "
        "FOR INSERT WITH CHECK ("
        "  app_is_operator()"
        "  OR household_id = ANY(app_household_ids())"
        "  OR ("
        "    identity_id = app_identity_id()"
        "    AND app_household_creator(household_id) = app_identity_id()"
        "    AND NOT app_household_has_any_membership(household_id)"
        "  )"
        ")"
    )

    # --- households_addresses: direct household_id ownership, same shape
    # as 20260720_0041's _HOUSEHOLD_SCOPED_TABLES. ---
    op.execute("ALTER TABLE households_addresses ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE households_addresses FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY households_addresses_isolation ON households_addresses "
        "USING (app_is_operator() OR household_id = ANY(app_household_ids())) "
        "WITH CHECK (app_is_operator() OR household_id = ANY(app_household_ids()))"
    )

    # --- orders_order_lines / payments_attempts: no customer_identity_id
    # of their own -- EXISTS against orders_orders, which already carries
    # the real customer-facing ownership check (20260720_0041). ---
    for table in _CHILD_TABLES_VIA_ORDER:
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

    # --- orders_shelf_life_exceptions: two hops (order_line -> order) to
    # the same customer_identity_id ownership check. ---
    op.execute("ALTER TABLE orders_shelf_life_exceptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE orders_shelf_life_exceptions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY orders_shelf_life_exceptions_isolation ON orders_shelf_life_exceptions "
        "USING (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM orders_order_lines ol JOIN orders_orders o ON o.id = ol.order_id"
        "  WHERE ol.id = orders_shelf_life_exceptions.order_line_id"
        "   AND o.customer_identity_id = app_identity_id()"
        ")) "
        "WITH CHECK (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM orders_order_lines ol JOIN orders_orders o ON o.id = ol.order_id"
        "  WHERE ol.id = orders_shelf_life_exceptions.order_line_id"
        "   AND o.customer_identity_id = app_identity_id()"
        "))"
    )

    # --- wallet ledger: no household_id of their own -- EXISTS against
    # wallet_accounts, which is already household-scoped (20260720_0041). ---
    op.execute("ALTER TABLE wallet_credits ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE wallet_credits FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY wallet_credits_isolation ON wallet_credits "
        "USING (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM wallet_accounts wa WHERE wa.id = wallet_credits.wallet_account_id"
        "   AND wa.household_id = ANY(app_household_ids())"
        ")) "
        "WITH CHECK (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM wallet_accounts wa WHERE wa.id = wallet_credits.wallet_account_id"
        "   AND wa.household_id = ANY(app_household_ids())"
        "))"
    )

    op.execute("ALTER TABLE wallet_debits ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE wallet_debits FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY wallet_debits_isolation ON wallet_debits "
        "USING (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM wallet_accounts wa WHERE wa.id = wallet_debits.wallet_account_id"
        "   AND wa.household_id = ANY(app_household_ids())"
        ")) "
        "WITH CHECK (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM wallet_accounts wa WHERE wa.id = wallet_debits.wallet_account_id"
        "   AND wa.household_id = ANY(app_household_ids())"
        "))"
    )

    op.execute("ALTER TABLE wallet_debit_allocations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE wallet_debit_allocations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY wallet_debit_allocations_isolation ON wallet_debit_allocations "
        "USING (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM wallet_credits wc JOIN wallet_accounts wa ON wa.id = wc.wallet_account_id"
        "  WHERE wc.id = wallet_debit_allocations.wallet_credit_id"
        "   AND wa.household_id = ANY(app_household_ids())"
        ")) "
        "WITH CHECK (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM wallet_credits wc JOIN wallet_accounts wa ON wa.id = wc.wallet_account_id"
        "  WHERE wc.id = wallet_debit_allocations.wallet_credit_id"
        "   AND wa.household_id = ANY(app_household_ids())"
        "))"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS wallet_debit_allocations_isolation ON wallet_debit_allocations"
    )
    op.execute("ALTER TABLE wallet_debit_allocations DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS wallet_debits_isolation ON wallet_debits")
    op.execute("ALTER TABLE wallet_debits DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS wallet_credits_isolation ON wallet_credits")
    op.execute("ALTER TABLE wallet_credits DISABLE ROW LEVEL SECURITY")

    op.execute(
        "DROP POLICY IF EXISTS orders_shelf_life_exceptions_isolation "
        "ON orders_shelf_life_exceptions"
    )
    op.execute("ALTER TABLE orders_shelf_life_exceptions DISABLE ROW LEVEL SECURITY")

    for table in _CHILD_TABLES_VIA_ORDER:
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS households_addresses_isolation ON households_addresses")
    op.execute("ALTER TABLE households_addresses DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY households_memberships_insert ON households_memberships")
    op.execute(
        "CREATE POLICY households_memberships_insert ON households_memberships "
        "FOR INSERT WITH CHECK ("
        "  app_is_operator()"
        "  OR household_id = ANY(app_household_ids())"
        "  OR identity_id = app_identity_id()"
        ")"
    )

    op.execute("DROP POLICY households_households_delete ON households_households")
    op.execute(
        "CREATE POLICY households_households_delete ON households_households "
        "FOR DELETE USING ("
        "  app_is_operator() OR id = ANY(app_household_ids()) OR created_by_identity_id = app_identity_id()"
        ")"
    )

    op.execute("DROP POLICY households_households_update ON households_households")
    op.execute(
        "CREATE POLICY households_households_update ON households_households "
        "FOR UPDATE USING ("
        "  app_is_operator() OR id = ANY(app_household_ids()) OR created_by_identity_id = app_identity_id()"
        ") WITH CHECK ("
        "  app_is_operator() OR id = ANY(app_household_ids()) OR created_by_identity_id = app_identity_id()"
        ")"
    )

    op.execute("DROP POLICY households_households_select ON households_households")
    op.execute(
        "CREATE POLICY households_households_select ON households_households "
        "FOR SELECT USING ("
        "  app_is_operator() OR id = ANY(app_household_ids()) OR created_by_identity_id = app_identity_id()"
        ")"
    )

    op.execute("DROP POLICY households_households_insert ON households_households")
    op.execute(
        "CREATE POLICY households_households_insert ON households_households "
        "FOR INSERT WITH CHECK (true)"
    )

    op.execute("DROP FUNCTION IF EXISTS app_household_has_any_membership(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_household_creator(uuid)")
