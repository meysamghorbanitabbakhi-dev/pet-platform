# Pet Platform — Gap-Closure Program: Final Engineering Handoff

**Branch:** `gap-closure-program` (off `main` at `666be27`) · **Date:** 2026-07-20 · **Commits:** 12

This program worked WS1 → WS12 in order against the mission brief's own instruction to inspect the
current branch first and reproduce or prove each finding before fixing it — several items turned
out to be already correctly implemented from prior work (noted per workstream below), and several
genuine, previously-undiscovered defects were found and fixed while implementing net-new scope, per
the brief's "do not postpone a discovered correctness defect" requirement. Every commit passed the
full backend test suite (grew from 389 to 403 tests across the program) before being made; the
suite is green at HEAD.

Status vocabulary used below matches the mission brief's own: `VERIFIED` (implemented, tested,
confirmed against a real backend/database), `EXTERNALLY_BLOCKED` (real work remains but requires an
external prerequisite this environment cannot provide), `DECISION_REQUIRED` (scoped down or skipped
by an explicit product/engineering decision made during this program, recorded here rather than
silently applied).

## Workstream-by-workstream

| WS | Title | Status | Summary |
|---|---|---|---|
| 1 | Central offer eligibility/checkout authorization | VERIFIED | Found and closed a real checkout-bypass: `reserve`/`concierge_only` offers were purchasable through the ordinary full-payment path. Added `allowed_modes` (a trusted-internal-command pattern, ADR-012), fixed offer-detail/list/search/reorder visibility, fixed a drifted `CheckConstraint`. Concurrency-tested (last-unit-oversell race). |
| 2 | Atomic order creation / workflow conversion | VERIFIED | Split `CheckoutService.create_order` into a no-commit core (`create_order_uncommitted`) and a thin committing wrapper, so replenishment/concierge conversions fold order creation into their own single atomic commit instead of a separate transaction that could leave orphaned state on a crash. Proved via fault-injection tests (simulate a crash mid-flow, assert nothing orphaned, assert retry still succeeds). |
| 3 | Reserve-now completion | VERIFIED | `approve_and_convert_reservation` now re-validates availability/capacity/offer-state at conversion time, not just proposal time, closing a real race where an offer paused or exhausted between operator proposal and customer approval could still convert. |
| 4 | Replenishment reservations | VERIFIED | Added the operator monitoring/correction surface (list/detail/invalidate) that reserve-now already had but replenishment didn't; added the same crash-fault-injection proof as WS2. |
| 5 | Concierge offer security/lifecycle | VERIFIED | Found and fixed a real bug: `decline_offer`'s discovered-expiry branch flushed but never committed the transition, silently losing it on the route's error response (accept's matching branch already self-committed correctly). Closed a test-coverage gap (no test verified non-operators are rejected from operator-only concierge routes). Everything else (price-snapshot immutability, refresh-version semantics, cross-household non-enumeration) was already correct. |
| 6 | Purchasing-batch operational completion | VERIFIED | Removed the unsafe threshold-of-one fallback for unconfigured aggregated-route offers (ADR-006 amendment); added whole-batch cancellation, conservatively scoped to zero-allocation batches. Investigated and *reverted* a deadline-enforcement change after its own test caught a real DB-invariant conflict — documented as a considered, not silently applied, decision. Found and fixed a self-inflicted regression (a WS1 test file lacked the cleanup fixture pattern needed to avoid breaking a migration-downgrade test in the shared test database). |
| 7 | Shelf-life exception correctness | VERIFIED | Replaced the permanent one-shot exception constraint with a partial unique index allowing re-proposal after decline/expiry (ADR-007's own documented deferred limitation, now closed); required a positive discount; moved the hardcoded 72-hour response window to a settings field; added a delivery-time guard rejecting an already-expired confirmed lot. |
| 8 | Inventory estimate data integrity | VERIFIED | Found and fixed a real bug: the replay-safety check compared only 4 of 6 material inputs, so a request that changed `feeding_context`/`daily_portion_grams` while keeping the same remaining-quantity facts was wrongly treated as a safe replay and returned a stale estimate. Replaced with a canonical, algorithm-versioned request hash covering every material input. |
| 9 | Trust evidence / authorization defense-in-depth (RLS) | VERIFIED | The largest item: implemented real PostgreSQL row-level security, reversing ADR-011's prior deferral. Found that the deferral's stated blocker was worse than described — the app's DB role is a Postgres superuser, which unconditionally bypasses RLS regardless of policy. Created a genuinely unprivileged role, per-request session context (`set_config`, re-applied every transaction), and policies matched against each table's *real* application-layer authorization column (found by reading routes, not assumed from schema — `orders_orders`/`reservations_reservations`/`concierge_offers` are customer-identity-scoped, not household-scoped, despite carrying a `household_id` column). Two bootstrap-case bugs found and fixed via the test suite itself, not review. Proven with tests that query the app-role connection directly, showing cross-household data is invisible even with no application-layer check involved. **Deliberately out of scope, documented as follow-up**: ~15 child tables with no direct household/customer-identity column of their own (order lines, wallet ledger entries, event/audit logs, etc.), each needing its own individually-verified policy. |
| 10 | Versioned commercial event model + trustworthy KPIs | DECISION_REQUIRED (skipped) | Investigated: the existing KPI module already computes 17 metrics via direct SQL against live tables, each with its own honestly-documented point-in-time limitation. Migrating all 17 to event-sourced computation (immutable price snapshots, computable margin via new cost capture) is comparable in scope to WS9. Asked; the explicit decision was to skip this workstream entirely for this program rather than a rushed partial migration. **Nothing was changed in this area.** |
| 11 | Frontend/accessibility/real E2E | VERIFIED (bounded) | Audited "missing customer/operator surfaces from WS3-7" against what actually exists rather than assuming: replenishment, concierge, and shelf-life exceptions each already have full customer UI from prior work; reserve-now is the one genuine gap, left unbuilt since the feature stays policy-disabled. Took real-backend E2E from 2 to 4 covered journeys (T8, T10, operator-KPIs, shop-discovery) with axe-core on every page state; fixed a real compatibility gap the WS9 work created in the E2E harness (`DATABASE_APP_URL` wasn't wired through). **7 of 11 journeys still have no real-backend E2E; no manual screen-reader audit was attempted** (not achievable without eyes/ears — automated axe-core is the honest substitute, documented as such, not claimed equivalent). |
| 12 | Production readiness / external integrations | VERIFIED where possible / EXTERNALLY_BLOCKED where not | Real load-test evidence (150-offer catalog, fresh database — the first attempt against this session's own polluted shared dev DB was discarded as unrepresentative and documented as such). Re-rehearsed backup/restore against the current (RLS-bearing) schema; found and documented a genuine new operational gap (the RLS role is cluster-level, not captured by `pg_dump`, so a fresh-cluster disaster-recovery restore needs an explicit extra step). Provider certification (Zarinpal/Payamak) remains genuinely `EXTERNALLY_BLOCKED`: `ZARINPAL_MERCHANT_ID` is empty in every environment available this session; the existing runbook checklist is correct and ready to execute once real credentials exist, but cannot be executed here. |

## Rollout register — policy flags disabled by default

Every flag below defaults to `false`/off in `.env.example` and every environment this program had
access to; none were enabled as part of this program, consistent with the accepted fact that
delivery commitment, OTP obsolescence, and these flags' disabled state are pre-agreed and out of
this program's authority to change.

| flag | default | gates | prerequisite before enabling |
|---|---|---|---|
| `reserve_now_enabled` | `false` | Reserve-now propose/reconfirm/approve flow (WS3) | A customer-facing reservation UI does not exist yet (WS11 finding) — enabling the backend flag alone would expose an API with no UI in front of it. |
| `replenishment_reservation_enabled` | `false` | Auto-reorder reservation flow (WS4) | Customer/operator UI exists and is tested; product sign-off on the reorder cadence/lead-time defaults (`replenishment_reservation_lead_days`, `_approval_window_hours`) is the remaining gate. |
| `concierge_offers_enabled` | `false` | Verified concierge sourcing offer lifecycle (WS5) | Customer/operator-API surface exists and is tested (no operator UI, consistent with this repo's existing operator-API-only precedent); product sign-off on launch is the remaining gate. |
| `late_credit_enabled` / `late_credit_customer_visible` | `false` / `false` | Late-delivery wallet credit issuance and its customer visibility | Independent from this program's scope; unchanged. |
| `delay_compensation_customer_visible` | `false` | Customer-visible delay compensation messaging | Independent from this program's scope; unchanged. |
| `cancel_after_sourcing_enabled` | `false` | Customer self-service cancellation after sourcing begins | Independent from this program's scope; unchanged. |
| `refund_self_service_enabled` / `replacement_self_service_enabled` / `substitution_self_service_enabled` | `false` each | Customer self-service order remediation paths | Independent from this program's scope; unchanged. |
| `push_notifications_enabled` | `false` | Push notification delivery | Independent from this program's scope; unchanged. |

New in this program, operational (not product) rollout requirements:

| item | requirement |
|---|---|
| `DATABASE_APP_URL` (WS9) | **Hard deployment prerequisite, not optional.** Must be set to a real password before `alembic upgrade head` runs in any environment adopting this program's changes — the migration that creates this role uses whatever is currently configured, and the application cannot authenticate to its own database with the placeholder value. See `docs/runbooks/launch.md`. |

## What full-scope acceptance would still require

- WS9's ~15 out-of-scope child tables getting their own individually-verified RLS policies.
- WS10 (event-sourced KPIs) in full, or a re-scoped bounded version, per further product direction.
- WS11's remaining 7 journeys' real-backend E2E, reserve-now's customer UI (if the flag is ever
  approved for launch), and a genuine manual accessibility pass by a human.
- WS12's authenticated/write-path load testing, a fresh-cluster disaster-recovery rehearsal
  (exercising the newly-documented RLS-role recreation step for real), and real provider
  certification once Zarinpal/Payamak credentials exist.

## Verification

Full backend suite green at HEAD (403 tests, exit 0); frontend `pnpm typecheck`, `pnpm lint`,
`pnpm test` (250 tests) all clean; `pnpm test:e2e:real-backend` (4 tests, real backend + Postgres +
axe-core) green. No skipped, weakened, or deleted tests anywhere in this program — every behavior
change that touched an existing test's assertion is documented at the point of change with why the
old assertion encoded now-superseded behavior, not silently patched.
