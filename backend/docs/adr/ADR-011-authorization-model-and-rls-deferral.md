# ADR-011: Application-layer authorization model; PostgreSQL RLS deferred

**Status:** Accepted for Workstream 5E (2026-07-20)

## Context

A systematic audit of every sensitive route (household-scoped customer resources and
operator-only routes) found that authorization in this codebase is enforced **exclusively at
the application layer**: each route calls a per-resource ownership check
(`require_household_membership`/`_household_access`, `require_pet_access`/`_pet_access`, or a
direct `X.customer_identity_id != identity.id` / `X.household_id != household.id` comparison)
before returning data, and a foreign-household/foreign-customer request returns `404` — the
same response an unknown id would produce (the "non-enumerating 404" convention used
throughout this codebase). Operator routes are role-scoped via the `CurrentOperator`
dependency, which every route under `/operator/*` was confirmed to declare.

No PostgreSQL Row-Level Security (RLS) policy exists anywhere in this codebase. No migration
creates a policy, no model or ADR references RLS, and no prior document records a decision to
adopt or skip it — it was never evaluated, not evaluated-and-declined.

## Decision

RLS remains **deferred, not adopted**, for this release. Authorization stays exclusively an
application-layer responsibility. This ADR exists so that stays a recorded, conscious decision
rather than an unexamined gap, and so a future team has the tradeoff written down instead of
having to rediscover it.

### Why defer rather than adopt now

- The platform has a single database role (the API's own connection) for all application
  queries; there is no separate low-privilege role per tenant/household that RLS's usual
  session-variable-based policies (`current_setting('app.household_id')`) would attach to.
  Introducing that role split, session-variable plumbing through the connection-pooled async
  SQLAlchemy engine, and a policy per household-scoped table is a substantial, cross-cutting
  change, not a small addition.
- Every session already flows through `SessionFactory`/`get_db_session`, which does not
  currently set any per-request session-local context RLS policies could read from. Adding it
  requires touching the request lifecycle (middleware or dependency) for every route, not just
  the sensitive ones — a correctness-critical change that itself needs its own careful design
  and test pass, which is out of scope for closing this workstream's existing test-coverage
  gaps.
- The immediate, higher-value fix identified by the audit was **test coverage** of the
  existing application-layer checks (see the Workstream 5E test additions), not a second
  enforcement layer. Several sensitive routes had the ownership check in code but no test
  proving a foreign household actually gets `404` — that is the gap this workstream closes.

### Why this is a real, tracked risk and not a non-issue

RLS is standard defense-in-depth specifically because application-layer checks can regress
silently: a future route that forgets to call `require_household_membership`, or a new query
added to an existing handler that bypasses the household filter, would currently be caught only
by code review and the test suite — never by the database itself. The operator-role audit found
this exact structural risk already present in a milder form: `CurrentOperator` is applied
correctly on every current operator route, but nothing except test coverage and review discipline
would catch a *future* route that omits it. RLS would catch that class of regression
automatically, at the data layer, regardless of which route or query introduced it.

## Consequences

- Every household-scoped and pet-scoped route must continue to call its ownership check
  explicitly; there is no fallback safety net if one is missed. Code review for new routes
  touching household/pet/customer-owned resources must treat the ownership check as
  mandatory, not optional.
- Workstream 5E adds behavioral (real HTTP request, real second household) tests for
  previously-untested sensitive routes specifically because this is the only enforcement layer
  that exists; test coverage is not a "nice to have" here, it is the primary safety net for
  this entire authorization model until/unless RLS is adopted.
- If a future team adopts RLS, this ADR's context section documents the concrete blockers
  (single DB role, no per-request session-local context) to resolve as part of that work,
  rather than starting from zero.
- This decision should be revisited if the platform ever needs a security posture that assumes
  application-code bugs happen (e.g. a compliance requirement for database-enforced tenant
  isolation) — at that point, the cost analysis above should be redone against the current
  codebase, not this snapshot.

## Amendment (2026-07-20) — gap-closure program, Workstream 9

RLS is no longer deferred. This section records what was actually built, the sharper problem
investigation surfaced beyond what the original deferral anticipated, and what is deliberately
still out of scope.

### The real blocker was sharper than "single database role"

Investigating adoption confirmed the original context (no per-request session-local context) but
also found something the original ADR didn't: `database_url`'s role (`pet_platform` in every
environment set up so far) is a Postgres **superuser**. Superusers unconditionally bypass row
security — no policy, no `FORCE ROW LEVEL SECURITY`, can override that. Every RLS policy this
program could have written would have been silently inert against that role regardless of how
carefully it was designed. This is why migration `20260720_0040` exists: it creates
`settings.database_app_url`'s role — ordinary `LOGIN`, explicit `NOSUPERUSER NOBYPASSRLS` — and
`app/db/session.py`'s request-serving engine (`app_engine`/`AppSessionFactory`, used by
`get_db_session`) connects as it instead. `engine`/`SessionFactory` (superuser) are unchanged and
still used by migrations and background scheduler jobs (`expire_stale_offers` and similar sweeps
are trusted system code crossing every household by design, not scoped to a single identity RLS
could restrict them to) and by every test file's direct-session fixture construction.

**Operational consequence**: a production deployment must provision this role (or let
`alembic upgrade head` do it) *and* set a real `DATABASE_APP_URL` password *before or during* this
migration's rollout — the placeholder in `.env.example` is exactly that, a placeholder, matching
this codebase's existing convention for `database_url`'s own default. If `DATABASE_APP_URL` is
left unset in an environment that has otherwise applied these migrations, the application's own
database connections will fail outright (the role would either not exist, per the app's default
guess, or exist with a password the app doesn't know) — this is a hard startup dependency now, not
a soft-fail security enhancement.

### Session context: SET LOCAL via set_config(), not literal SET

`app/api/dependencies.py`'s `apply_rls_context` (called from a new `_identity_with_rls_context`
wrapper, described below) issues `SELECT set_config('app.household_ids', $1, true)` — not
`SET LOCAL app.household_ids = $1` directly. Postgres's `SET`/`SET LOCAL` grammar does not accept a
bind parameter in place of its value; `set_config(name, value, is_local)` is an ordinary function
call and takes one normally, with `is_local=true` giving the identical transaction-scoped
semantics. This was found the hard way — the first version of this migration passed the full test
suite's smoke checks but failed on every real HTTP request with a Postgres syntax error, because
`exec_driver_sql`/`text()` happily compiles a bind parameter into a prepared-statement placeholder
regardless of whether the target SQL construct can accept one there.

Three session variables: `app.is_operator`, `app.identity_id`, `app.household_ids` (comma-separated
UUIDs, recomputed fresh from `HouseholdMembership` on *every* request — never cached across
requests, so a membership change takes effect on the very next request). `app/db/session.py`
registers a dedicated `_RLSSession` subclass (not the generic `sqlalchemy.orm.Session`, so this
plumbing cannot affect an unrelated engine or session a test constructs) with an `after_begin`
event that re-issues these three `set_config` calls at the start of *every* transaction the
session opens, not just the first — `SET LOCAL`/`set_config(..., true)` only lasts one transaction,
and a route that commits mid-request and keeps querying afterward would otherwise silently lose
RLS context for everything after that commit.

### Composable with the existing test suite's auth-faking pattern

This codebase's ~100 existing HTTP-level tests almost universally fake authentication via
`app.dependency_overrides[get_current_identity] = lambda: some_identity`, never a real bearer
token. `apply_rls_context` is deliberately **not** called inside `get_current_identity` itself —
it is called by a separate outer dependency, `_identity_with_rls_context`, which depends on
`get_current_identity` and still runs even when only the inner function is overridden (FastAPI
substitutes overrides per-dependency-callable, not per-dependency-subtree). `CurrentIdentity` now
resolves through this wrapper. This is *why* the existing ~400-test suite needed zero test-file
changes to keep passing under RLS: every one of those overrides still gets correct, real RLS
context applied for whichever identity it injected.

### Per-table scoping: household_id is not always the right column

The initial policy design assumed every table with a `household_id` column should be scoped by
household membership (`household_id = ANY(app_household_ids())`). Testing against the real
application routes (not an assumption from the schema alone) found this wrong for three tables:
`orders_orders`, `reservations_reservations` (reserve-now), and `concierge_offers`. Each carries a
`household_id` column, but every customer-facing route touching them authorizes by
`row.customer_identity_id != identity.id` — the *specific purchasing/requesting customer*, not
"any member of the household." A second household member the application itself would `404` for
could have read the row directly if its RLS policy had used `household_id` instead. These three
tables' policies check `customer_identity_id = app_identity_id()` instead — RLS matching the real
application semantic, not a looser or stricter one. `inventory_units`, `inventory_reorder_snoozes`,
`pets_pets`, `replenishment_reservations`, `support_customer_requests`, and `wallet_accounts` were
confirmed (also by reading their routes, not assumed) to genuinely be household-membership-scoped
via `_household_access`/`require_household_membership`, and keep the household_id-based policy.
`catalog_availability_subscriptions` is `identity_id`-scoped (its `household_id` column is
nullable, optional delivery-address metadata, not the ownership column).

### Two bootstrap edge cases, both found by testing against the real routes

1. **`households_memberships`'s own SELECT policy was circular.** `apply_rls_context`'s query to
   *discover* a customer's `household_ids` reads this table — but its SELECT policy originally only
   allowed `household_id = ANY(app_household_ids())`, which is exactly the value being computed.
   Fixed by adding `OR identity_id = app_identity_id()` to the SELECT (and INSERT) policy, and by
   setting `app.identity_id`/`app.is_operator` *before* running that discovery query (previously
   they were set after, which would have left `app_identity_id()` null during the very query that
   needed it).
2. **Postgres evaluates `INSERT ... RETURNING` output against the SELECT policy, not just the
   INSERT policy's `WITH CHECK`.** SQLAlchemy issues `RETURNING` automatically for any row with a
   `server_default` column (`created_at`/`updated_at`, via `TimestampMixin` — effectively every
   table in this codebase), to populate the in-memory object after insert. `create_household`
   inserts the `Household` row, then the `HouseholdMembership` row proving access to it, as two
   separate statements — the membership does not exist yet at the moment the household's own
   `RETURNING` is evaluated, so no live membership check could satisfy the SELECT policy at that
   exact instant. `households_households` gained `created_by_identity_id` (migration
   `20260720_0042`, nullable, never backfilled — a household can have several members and no
   pre-existing row recorded who acted first, so it cannot be honestly reconstructed) specifically
   to give the SELECT/UPDATE/DELETE policies a fact available at that exact moment, mirroring
   `households_memberships`' own `identity_id` fallback.

Both of these were caught by `tests/integration/test_row_level_security.py`, not inferred from
review — the honest starting expectation is that other bootstrap-shaped writes into RLS-protected
tables can hit the same `RETURNING`-vs-SELECT-policy interaction if a future workstream adds RLS to
a table whose row isn't already visible to its own creator at insert time.

### Scope: what is, and is not, RLS-protected now

Enabled (migration `20260720_0041` + `20260720_0042`): `inventory_units`,
`inventory_reorder_snoozes`, `pets_pets`, `replenishment_reservations`,
`support_customer_requests`, `wallet_accounts` (household-membership-scoped);
`orders_orders`, `reservations_reservations`, `concierge_offers`
(customer-identity-scoped); `catalog_availability_subscriptions` (identity-scoped);
`households_households` and `households_memberships` (both, with the bootstrap-case handling
above).

**Deliberately not enabled this pass**: child tables with no `household_id`/`customer_identity_id`
of their own — order lines, consumption assignments, wallet ledger entries (credits/debits/debit
allocations), event/audit-log tables (`reservations_events`, `replenishment_reservation_events`,
`concierge_offer_events`, `support_customer_request_status_audit`), `food_estimation_estimates`,
`orders_shelf_life_exceptions`, `pets_breed_selections`, `payments_payment_attempts`. Each would
need its own considered `EXISTS`-against-parent policy, individually verified the way the tables
above were — bundling another ~15 tables into this pass without that same verification would trade
the low-risk, tested core this amendment delivers for a rushed, unverified one, which is a worse
outcome than a narrower, honest scope. A future workstream extending RLS to these should expect to
rediscover instances of the same two classes of problem found here (wrong scoping column assumed
from the schema alone; `RETURNING` vs. a not-yet-established fact at insert time) and budget for
them, not treat this amendment's core as a template to blindly repeat.

Also out of scope, deliberately: purely operator-facing tables (`purchasing_batches` and its
children, `trust_*` evidence tables, price-intelligence tables). These have no customer-facing read
path to defend, and `purchasing_batches` in particular intentionally pools demand across households
by design — household-scoping it would be a modeling error, not a security fix.
