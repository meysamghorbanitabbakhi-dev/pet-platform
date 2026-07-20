"""Enable row-level security on household/customer-scoped tables (Workstream 9).

Revision ID: 20260720_0041
Revises: 20260720_0040

ADR-011's amendment: this is the real enforcement layer the prior ADR
deferred. Application-layer ownership checks (require_household_membership,
_household_access, direct customer_identity_id/household_id comparisons)
remain the primary, tested authorization mechanism -- these policies are
defense-in-depth, catching the class of regression ADR-011 named as the
real risk: a future route or query that forgets its ownership check.

Three helper functions read this request's session-local context (set by
app/api/dependencies.py's apply_rls_context, applied on every transaction
by app/db/session.py's after_begin event): app_is_operator() (operators
see everything, matching their existing cross-household job function),
app_household_ids() (a customer's own household memberships, recomputed
fresh every request), app_identity_id() (the authenticated identity
itself, for the one table -- household membership -- where "am I the
subject of this row" matters independently of household membership).

Scope of this migration: every household/customer-scoped table with a
customer-facing route, split by which column that route actually
authorizes against -- household_id for tables gated by household
membership (inventory, pets, replenishment requests, support requests,
wallet accounts, household membership itself), customer_identity_id for
tables gated by the specific requesting customer regardless of who else
is in their household (orders, reserve-now reservations, concierge
offers -- confirmed by reading each one's customer-facing routes, not
assumed from the household_id column those rows also happen to carry),
plus catalog_availability_subscriptions (identity_id-scoped for the same
reason -- household_id there is nullable optional metadata, not the
ownership column). Purely operator-facing tables (purchasing batches,
trust evidence, price intelligence) are deliberately out of scope: they
have no customer-facing read path to defend, and purchasing batches in
particular intentionally pool across households by design, so
household-scoping them would be a modeling error, not a security fix.
Child tables with no household_id of their own (order lines, consumption
assignments, wallet ledger entries, event/audit logs, etc.) are also out
of scope for this pass -- each needs its own considered EXISTS-based
policy against its parent, verified individually, and bundling ~15 more
tables into this migration without that same care would trade the
low-risk, well-tested core this pass delivers for a rushed, unverified
one. Recorded as explicit follow-up in the ADR-011 amendment, not a
silent gap.

`FORCE ROW LEVEL SECURITY` is applied even though the app-role migration
(20260720_0040) already means these tables' owner (the migration role)
differs from the role RLS needs to constrain -- explicit here so this
stays correct even if table ownership ever changes.

Downgrade drops every policy and the three helper functions and disables
RLS; lossless, since nothing here rewrites data.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260720_0041"
down_revision: str | None = "20260720_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables whose customer-facing routes authorize by household membership
# (app.api.routes.pet_life._household_access / require_household_membership)
# -- any member of the household may access these, matching that check.
_HOUSEHOLD_SCOPED_TABLES = (
    "inventory_units",
    "inventory_reorder_snoozes",
    "pets_pets",
    "replenishment_reservations",
    "support_customer_requests",
    "wallet_accounts",
)

# Tables whose customer-facing routes authorize by the specific
# purchasing/requesting customer's own identity
# (`row.customer_identity_id != identity.id`), *not* household
# membership, even though the row also carries a household_id column --
# confirmed by reading every customer-facing route touching each of
# these (app/api/routes/commerce.py's order/reservation detail routes,
# app/api/routes/concierge_offers.py's customer routes). Scoping these
# by household_id instead would make RLS looser than the application
# layer it's supposed to backstop: a co-member the app itself would 404
# for could read the row directly if the DB policy allowed household_id
# instead. household_id stays an ordinary, non-RLS-restricted column on
# these tables for operator/reporting queries (operators bypass RLS
# entirely via app_is_operator()).
_CUSTOMER_IDENTITY_SCOPED_TABLES = (
    "orders_orders",
    "reservations_reservations",
    "concierge_offers",
)

# asyncpg cannot prepare a multi-statement string in one execute() call
# (unlike psycopg2's default), so each function/policy/table statement
# is its own op.execute() -- see the multiple separate calls below,
# rather than one larger SQL block.
_IS_OPERATOR_FUNCTION_SQL = """
CREATE FUNCTION app_is_operator() RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT COALESCE(current_setting('app.is_operator', true), 'false') = 'true'
$$
"""

_HOUSEHOLD_IDS_FUNCTION_SQL = """
CREATE FUNCTION app_household_ids() RETURNS uuid[]
LANGUAGE sql STABLE AS $$
  SELECT CASE
    WHEN current_setting('app.household_ids', true) IS NULL
      OR current_setting('app.household_ids', true) = ''
    THEN ARRAY[]::uuid[]
    ELSE string_to_array(current_setting('app.household_ids', true), ',')::uuid[]
  END
$$
"""

_IDENTITY_ID_FUNCTION_SQL = """
CREATE FUNCTION app_identity_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.identity_id', true), '')::uuid
$$
"""


def upgrade() -> None:
    op.execute(_IS_OPERATOR_FUNCTION_SQL)
    op.execute(_HOUSEHOLD_IDS_FUNCTION_SQL)
    op.execute(_IDENTITY_ID_FUNCTION_SQL)

    for table in _HOUSEHOLD_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_household_isolation ON {table} "
            "USING (app_is_operator() OR household_id = ANY(app_household_ids())) "
            "WITH CHECK (app_is_operator() OR household_id = ANY(app_household_ids()))"
        )

    for table in _CUSTOMER_IDENTITY_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_customer_isolation ON {table} "
            "USING (app_is_operator() OR customer_identity_id = app_identity_id()) "
            "WITH CHECK (app_is_operator() OR customer_identity_id = app_identity_id())"
        )

    # households_households: policy is on `id`, not a `household_id`
    # column. INSERT is deliberately permissive -- a customer creating
    # their first household cannot yet have that household's id in their
    # own app_household_ids() (the membership row proving they belong to
    # it is created in the same transaction, immediately afterward); the
    # membership insert below is the actual access-granting step.
    op.execute("ALTER TABLE households_households ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE households_households FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY households_households_select ON households_households "
        "FOR SELECT USING (app_is_operator() OR id = ANY(app_household_ids()))"
    )
    op.execute(
        "CREATE POLICY households_households_insert ON households_households "
        "FOR INSERT WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY households_households_update ON households_households "
        "FOR UPDATE USING (app_is_operator() OR id = ANY(app_household_ids())) "
        "WITH CHECK (app_is_operator() OR id = ANY(app_household_ids()))"
    )
    op.execute(
        "CREATE POLICY households_households_delete ON households_households "
        "FOR DELETE USING (app_is_operator() OR id = ANY(app_household_ids()))"
    )

    # households_memberships: SELECT/UPDATE/DELETE follow the standard
    # household-membership rule, but SELECT and INSERT also allow a row
    # whose identity_id is the requester's own. This is not just the
    # bootstrap case (self-adding to a brand-new household not yet
    # reflected in app_household_ids()) -- SELECT needs it too, and for a
    # more fundamental reason: apply_rls_context's own query to *discover*
    # a customer's household_ids reads this table, before household_ids
    # is known for this transaction. Without the identity_id fallback,
    # that query would be filtered down to nothing by household_id =
    # ANY(app_household_ids()) (empty at that point) and no customer
    # could ever learn their own household_ids at all. It also composes
    # correctly with a future "invite another member" / "view my
    # household's members" flow (household_id already known) without
    # needing a separate policy for that case.
    op.execute("ALTER TABLE households_memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE households_memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY households_memberships_select ON households_memberships "
        "FOR SELECT USING ("
        "  app_is_operator()"
        "  OR household_id = ANY(app_household_ids())"
        "  OR identity_id = app_identity_id()"
        ")"
    )
    op.execute(
        "CREATE POLICY households_memberships_insert ON households_memberships "
        "FOR INSERT WITH CHECK ("
        "  app_is_operator()"
        "  OR household_id = ANY(app_household_ids())"
        "  OR identity_id = app_identity_id()"
        ")"
    )
    op.execute(
        "CREATE POLICY households_memberships_update ON households_memberships "
        "FOR UPDATE USING (app_is_operator() OR household_id = ANY(app_household_ids())) "
        "WITH CHECK (app_is_operator() OR household_id = ANY(app_household_ids()))"
    )
    op.execute(
        "CREATE POLICY households_memberships_delete ON households_memberships "
        "FOR DELETE USING (app_is_operator() OR household_id = ANY(app_household_ids()))"
    )

    # catalog_availability_subscriptions: identity_id-scoped, not
    # household_id (nullable there, optional metadata rather than the
    # ownership column) -- a subscription belongs to the customer who
    # asked to be notified, not to a household as such.
    op.execute("ALTER TABLE catalog_availability_subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE catalog_availability_subscriptions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY catalog_availability_subscriptions_isolation "
        "ON catalog_availability_subscriptions "
        "USING (app_is_operator() OR identity_id = app_identity_id()) "
        "WITH CHECK (app_is_operator() OR identity_id = app_identity_id())"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS catalog_availability_subscriptions_isolation "
        "ON catalog_availability_subscriptions"
    )
    op.execute("ALTER TABLE catalog_availability_subscriptions DISABLE ROW LEVEL SECURITY")

    for policy, table in (
        ("households_memberships_delete", "households_memberships"),
        ("households_memberships_update", "households_memberships"),
        ("households_memberships_insert", "households_memberships"),
        ("households_memberships_select", "households_memberships"),
    ):
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
    op.execute("ALTER TABLE households_memberships DISABLE ROW LEVEL SECURITY")

    for policy, table in (
        ("households_households_delete", "households_households"),
        ("households_households_update", "households_households"),
        ("households_households_insert", "households_households"),
        ("households_households_select", "households_households"),
    ):
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
    op.execute("ALTER TABLE households_households DISABLE ROW LEVEL SECURITY")

    for table in _CUSTOMER_IDENTITY_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_customer_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    for table in _HOUSEHOLD_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_household_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS app_is_operator()")
    op.execute("DROP FUNCTION IF EXISTS app_household_ids()")
    op.execute("DROP FUNCTION IF EXISTS app_identity_id()")
