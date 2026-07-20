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
