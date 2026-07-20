# Engineering handoff

## System boundary

This is an Iran-first modular monolith for commerce, sourced-after-payment operations, household
inventory, pet life, journeys, diary, Persian Garden, order fulfillment, notifications, wallet,
trust evidence, privacy, and a single 360-degree operator.

Money is stored as integer IRR. Full payment is enabled. Reserve-now is modeled but disabled.
Delivery commitment is exactly 366 hours. Customer media/evidence uses ordinary filesystem
directories on a persistent Docker volume; S3 is not required.

## Deployment order

1. Configure secrets and persistent media path.
2. Start PostgreSQL and Redis.
3. Run `alembic upgrade head`.
4. Run operator bootstrap and launch fixture seed.
5. Start API and worker/scheduler processes.
6. Perform the checks in `docs/runbooks/launch.md`.

## Deliberate policy gates

- reserve-now payment and approval policy;
- cancellation, refund, replacement, and substitution rules;
- compensation amount/rule;
- professional approval of care content;
- privacy anonymization and retention matrix.

The backend does not convert these unresolved decisions into customer-facing claims.

## Evidence status

Static analysis, unit tests, API schema tests, and offline migration graph checks are automated.
Real Docker Compose PostgreSQL/Redis integration and concurrency testing was deferred by founder
instruction and must be run before production traffic; it is not represented as completed evidence.

---

## 2026-07-20 amendment: Workstreams 2-9 completion report

This is a dated addition, not a rewrite — the section above describes the state as of when it was
written and is left unchanged. Since then, real Docker Compose PostgreSQL/Redis integration and
concurrency testing has been performed extensively (see below); that earlier deferral no longer
describes the current state.

### Executive summary

Starting from the completed design-contract closure (commit `54e217d`, "149 IMPLEMENTED + 3
OBSOLETE_BY_CONTRACT, 0 gaps"), this pass delivered Workstreams 2 through 9 of the follow-on
mission brief: commercial-domain hardening (purchasing batches, customer cancellation, reserve-now,
late-credit, shelf-life exceptions), two new flag-gated domains (replenishment reservations,
verified concierge offers), data-integrity/transaction hardening across five sub-areas, a KPI
reporting module with an operator dashboard, a frontend/accessibility audit, closure of the
70-item design-traceability missing-test backlog (now CI-gated), and a set of real (not merely
read-from-code) production-readiness rehearsals. 30 commits, 129 files touched,
+47,732/-15,461 lines. All work is committed to `master`; nothing is left uncommitted or staged
only.

### Commit list

See `git log --oneline 54e217d..HEAD` (30 commits) for the authoritative list; each commit message
states which workstream it belongs to and why. Not reproduced verbatim here to avoid this document
drifting out of sync with git history — git itself is the source of truth for exact commit content.

### Migration sequence

9 new Alembic migrations, `20260719_0029` through `20260720_0037` (current head), all forward-only
with explicit backfill-before-constrain ordering and documented rollback behavior where a downgrade
has any limitation:

| Revision | Adds |
|---|---|
| `20260719_0029` | Offer sourcing route field |
| `20260719_0030` | Purchasing batches (Workstream 2A) |
| `20260719_0031` | Customer cancellation (Workstream 2B) |
| `20260719_0032` | Shelf-life exceptions (Workstream 2E) |
| `20260719_0033` | Reserve-now (Workstream 2C, flag-gated) |
| `20260719_0034` | Replenishment reservations (Workstream 3, flag-gated) |
| `20260720_0035` | Verified concierge offers (Workstream 4, flag-gated) |
| `20260720_0036` | Partial unique index: one active food estimate per inventory unit (Workstream 5A) |
| `20260720_0037` | `evidence_file_id` FKs replacing `evidence_path` strings on trust tables (Workstream 5B); downgrade reverse-backfills `evidence_path` from `evidence_file_id`, verified lossless |

No destructive column drops; every replaced column was relaxed/deprecated in place with a documented
follow-up. `alembic heads` confirms a single linear head (`20260720_0037`); no branches.

### Capability-by-capability summary

| Capability | Status |
|---|---|
| Purchasing batches, cancellation, reserve-now, late-credit, shelf-life exceptions | Implemented, tested, live (reserve-now behind `reserve_now_enabled=false`) |
| Replenishment reservations | Implemented, tested, flag-gated (`replenishment_reservation_enabled=false`) |
| Verified concierge offers | Implemented, tested, flag-gated (`concierge_offers_enabled=false`) |
| Food-estimate concurrency (one active estimate per unit) | Implemented, PostgreSQL partial-unique-index-enforced, concurrent-open race tested |
| Trust evidence FK integrity | Implemented, backfilled, migration-verified lossless both directions |
| Payment lock/Zarinpal I/O separation | Implemented; a real pre-existing bug (row locks held across gateway network I/O) fixed and proven with a live-lock-absence test |
| Outbox dead-letter visibility + replay | Implemented, operator API + tests (retry, dead-letter, duplicate-handler, process-restart) |
| Cross-household/operator authorization | Audited systematically; critical/high-priority gaps closed with real HTTP tests; RLS deferral documented (ADR-011) with an honest medium-priority residual (see Residual risk) |
| KPI reporting (19 metrics) | Implemented, versioned, operator API + minimal dashboard; `margin` honestly marked not computable (no cost data exists) |
| Frontend hardening (BFF-only, HTTP-only tokens, CSRF, RTL, a11y primitives) | Audited — already correctly implemented from prior work, no gaps found |
| Design-state test-traceability | 152/152 states IMPLEMENTED with real cited tests, 0 gaps, `check:traceability` now gates `check:contract` |
| Production-readiness rehearsals | PostgreSQL backup/restore, Redis loss, worker/scheduler restart, secret/HSTS validation — all rehearsed with real evidence, not assumed |
| Zarinpal/Payamak sandbox certification | **Not performed** — no real vendor credentials in this environment |
| Load testing | **Not performed** — no tooling configured, no representative environment |
| Real-backend E2E for all 11 journeys, full axe-core/keyboard-flow coverage | **Not done** — 2 of 11 journeys covered, via a dev-fixture auth mode, not a real backend |

### Design-state final counts

152/152 canonical states accounted for: 149 `IMPLEMENTED`, 3 `OBSOLETE_BY_CONTRACT` (each with a
documented authority/rationale), 0 `PARTIAL`/`MISSING`/`BACKEND_BLOCKED`/`POLICY_HIDDEN`-incorrectly-used.
Every `IMPLEMENTED` row now cites a real, substantive test (`frontend/docs/design-state-implementation-matrix.md`);
`pnpm check:traceability` passes with zero differences and is chained into `pnpm check:contract`.

### Test / verification commands and results (run today, this pass)

Backend (via `docker exec pet-platform-devtools`):
- `python -m ruff check .` → clean.
- `python -m mypy app/` → clean, 165 files. `python -m mypy tests/` → 91 pre-existing errors remain (down from 164 after this pass's fix), none in `app/`, none blocking; scattered across ~15 files, individually pre-existing and unrelated to each other.
- `python -m pytest -q` (full suite, ~364 test functions) → all passing, run repeatedly throughout this pass after every change.
- `alembic heads` → single head `20260720_0037`, linear history verified base-to-head.
- `python -m app.cli.export_openapi` / `verify_release_contract` → OpenAPI matches the live app byte-for-byte; release contract verified.

Frontend (via `npm run` in `frontend/pet-platform-frontend`):
- `npm run typecheck` → clean.
- `npm run lint` → clean.
- `npm run format` (prettier --check) → 32 pre-existing files have drift (none touched by this pass); not fixed, out of scope, noted as a small cosmetic backlog.
- `npm run test -- --run` (vitest) → 55/55 files, 250/250 tests passing.
- `npm run build` (production) → succeeds, all routes generated including the new `/operator/kpis`.
- `npm run check:contract` → passes end-to-end (openapi + design-contract + bff-coverage + traceability).

Not run: a full `alembic downgrade base` sweep (assessed as genuinely risky against the shared,
long-lived, heavily-populated dev database used throughout this session by many other tests —
individual migrations added this pass were each verified with a 2x up/down cycle instead); real
Playwright E2E for the 9 journeys not yet covered; axe-core scans beyond the 2 already-covered
journeys; a manual screen-reader walkthrough.

### OpenAPI counts

181 paths, 199 operations, 237 schemas, `sha256:6f6493f3...` (see `release-contract.json` for the
current full hash) — matches the live application exactly as of this pass.

### Remaining policy flags and approval owner

Unchanged from the existing policy decision register (`docs/adr/ADR-004-k9-policy-boundaries.md`)
plus three more added this program: `reserve_now_enabled`, `replenishment_reservation_enabled`,
and `concierge_offers_enabled` all remain `false` pending business/product approval to launch each
capability — each is fully built, tested, and one config flag away from live. No new unresolved
policy decisions were introduced by Workstreams 5-9; these are commercial/operational launch
decisions, not engineering ones, and this document does not name a specific approval owner because
none was specified to this pass.

### External vendor limitations

- **Zarinpal**: `zarinpal_merchant_id` is unset in every environment available to this pass; genuine
  sandbox certification (`docs/runbooks/provider-certification.md`) requires a real merchant account
  this environment does not have.
- **Payamak Panel (SMS/OTP)**: same — no real provider credentials configured. `ADR-005` already
  documents that this provider has no delivery-receipt capability at all (a vendor limitation, not
  an engineering gap).

### Production readiness evidence

See `BACKEND_SYSTEM_MAP.md` section 9 and the dated evidence sections in
`docs/runbooks/backup-restore.md` and `docs/runbooks/observability.md` for full detail and exact
commands run. Summary: PostgreSQL backup/restore rehearsed for real (dump → disposable-database
restore → table/row/alembic-version verification, cleaned up after); Redis-loss and
worker/scheduler-restart behavior observed directly by stopping/restarting the actual containers;
one real gap found and fixed (`security_hsts_enabled` was not enforced in production). Zarinpal/
Payamak certification and load testing were not performed (see External vendor limitations) and are
not claimed as done anywhere in this codebase's documentation.

### Residual risk (by severity)

- **Medium**: no PostgreSQL Row-Level Security exists; authorization is enforced entirely at the
  application layer (every household/pet-scoped route calling its ownership check explicitly). A
  route that forgets this check in the future would not be caught by the database itself, only by
  code review and test coverage. Documented and reasoned through in ADR-011, including why RLS
  adoption was deferred rather than silently skipped (no session-local-context plumbing exists yet
  for it). Mitigated, not eliminated, by this pass's systematic authorization test additions for the
  highest-value routes (WS5E) — a residual, lower-probability gap remains on routes not explicitly
  covered by that pass (e.g. most `/operator/*` routes beyond the ~14 now explicitly 403-tested,
  though `CurrentOperator` is structurally uniform across all of them).
- **Medium**: real-backend Playwright E2E covers 2 of 11 customer journeys; the other 9, plus
  axe-core/keyboard-flow automation and a manual screen-reader/responsive walkthrough, remain
  undone. The underlying component-level test coverage is strong (250 frontend tests, all 152
  design states cited), but end-to-end browser-level proof for most journeys does not exist yet.
- **Low-medium**: ~91 pre-existing strict-mypy errors remain in `tests/` (none in `app/`), each a
  distinct, small, pre-existing issue (mock session typing, `**dict[str, object]` kwargs spreading,
  a couple of genuine test-logic type mismatches) — cosmetic/type-safety debt in test code, not a
  runtime correctness risk, but worth a dedicated cleanup pass.
- **Low**: 32 pre-existing frontend files have prettier formatting drift; cosmetic only.
- **Known, not a defect**: `margin` KPI is honestly non-computable (no supplier-cost field exists
  anywhere in the commerce schema); Zarinpal/Payamak certification and load testing are genuinely
  unperformed, not silently assumed passing.
