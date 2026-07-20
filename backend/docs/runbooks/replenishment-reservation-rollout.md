# Replenishment reservation rollout runbook

`replenishment_reservation_enabled` (`app/core/config.py`) is `false` by default. Enabling it is a
founder/product decision about how aggressively the platform should propose reorders on a
customer's behalf, not an engineering one — the underlying domain (creation rule, approval,
decline, expiry) is already built and tested. See ADR-009 for the architecture and
`pet_platform_product_decision_record.md` Part XI (Decisions 0.29-0.31) for the locked product
rules this implements. This runbook only covers how to enable the already-built domain safely
once approval exists.

## What the flag actually gates

`replenishment_reservation_enabled=true` makes every replenishment-reservation endpoint reachable
instead of returning `409 replenishment_reservation_disabled`:

- Customer: `GET /api/v1/pet-life/households/{household_id}/replenishment-reservations`,
  `GET /api/v1/pet-life/replenishment-reservations/{id}`,
  `POST /api/v1/pet-life/replenishment-reservations/{id}/approve`,
  `POST /api/v1/pet-life/replenishment-reservations/{id}/decline`.
- The scheduler's `_run_replenishment_scan_job` (creates/refreshes reservations) and
  `_run_replenishment_expiry_job` (`app/workers/scheduler.py`), neither of which is even
  *registered* while the flag is off.
- The `create_or_refresh_reservation_for_unit`/`invalidate_reservation_for_unit` calls inside the
  existing `POST /pet-life/inventory/{unit_id}/estimate/correct` and
  `POST /pet-life/inventory/{unit_id}/exhaust` endpoints are also skipped while the flag is off —
  those two endpoints otherwise behave exactly as they did before this workstream.
- Frontend: `src/features/inventory/inventory-opening.tsx`'s replenishment panel and
  `src/features/today/today-dashboard.tsx`'s pending-reservations banner both render nothing while
  `shouldRenderReplenishmentReservations(policy)` is false — no placeholder or disabled affordance
  is shown, matching this codebase's fail-closed policy-gating convention.

## Pre-enablement checklist

1. **Founder/product approval recorded**, specifically covering the three numeric policy
   parameters, all currently engineering defaults, not approved numbers:
   `replenishment_reservation_lead_days` (default 14, matches Decision 0.30's "14 days before
   predicted depletion" exactly — confirm this is still the intended figure before launch, not
   just before this pass), `replenishment_reservation_approval_window_hours` (default 48, matches
   Decision 0.31 exactly), and confirmation that showing the *live, informational* offer price
   before approval (rather than a locked/reconfirmed one — see ADR-009 point 5) is the intended
   customer experience.
2. **Test evidence exists.** `pytest tests/integration/test_replenishment_reservations.py` passes
   against a real PostgreSQL instance (`K10_RUNTIME_TESTS=1`, 27 tests). This covers: creation only
   from sufficient facts (estimate within lead time and a reorderable offer), no duplication on
   repeat scans, refresh-in-place on a worsened estimate without resetting the approval clock,
   terminal reservations never resurrected, approval at the live offer price with zero
   `PaymentAttempt` rows created, approval/decline idempotency, expiry with exactly one reminder,
   scheduler scan end-to-end, a concurrent-creation race (two simultaneous scan/correct-triggered
   attempts on the same unit never produce two rows), a concurrent approve-vs-decline race, HTTP
   gating, the full HTTP lifecycle, non-enumerating 404s across households, and the
   `correct_estimate`/`exhaust_inventory` hook wiring. Frontend: `pnpm test` (`src/lib/policy.test.ts`,
   `src/features/inventory/inventory-opening.test.tsx`, `src/features/today/today-dashboard.test.tsx`).
3. **Notification templates exist and are active** for `event_key="replenishment.reservation_created"`
   and `event_key="replenishment.reservation_expired"`, `channel="sms"` — the same
   `deliver_pending_sms` fail-closed requirement as every other templated notification in this
   codebase (`recipient_or_template_missing` otherwise, permanent failure, no retry). Neither
   template is seeded today (matching the pre-existing, not-yet-closed gap for
   `reservations.proposed`/`orders.shelf_life_exception_proposed` — the in-app channel works
   regardless; only SMS delivery is affected).
4. **Confirm at least some real offers are reorderable** (`status=active`,
   `stock_posture=sourced_after_payment`, `sourcing_capacity_status=open`) for the products
   customers actually have opened inventory units for — otherwise the scheduler will legitimately
   find nothing to propose, which will look like a bug but isn't one.

## Enabling

1. Set `REPLENISHMENT_RESERVATION_ENABLED=true` (and, if the approved values differ from the
   defaults, `REPLENISHMENT_RESERVATION_LEAD_DAYS` / `REPLENISHMENT_RESERVATION_APPROVAL_WINDOW_HOURS`)
   in the deployment secret manager. Restart the API process (customer endpoints and the
   `correct_estimate`/`exhaust_inventory` hooks) and the scheduler process (to register the two
   replenishment jobs) — `Settings` is process-cached, so a restart is the safe way to pick up the
   change everywhere.
2. Watch scheduler logs for `replenishment reservation scan result: {...}` and
   `expired N stale replenishment reservations`, cross-checked against
   `SELECT status, count(*) FROM replenishment_reservations GROUP BY status`.
3. Watch for `replenishment.reservation_created` / `replenishment.reservation_expired` outbox
   events dispatching successfully (`system_outbox_events` dead-letter count should stay at zero
   for these event types).
4. Spot-check that an approved reservation's resulting `Order` reaches `awaiting_payment` and that
   the customer actually completes payment through the existing, unmodified Zarinpal flow — no
   code path in this workstream auto-charges anything.

## Rollback

Turning `replenishment_reservation_enabled` back to `false` immediately 409s every
replenishment-reservation endpoint again, de-registers both scheduler jobs, and turns
`correct_estimate`/`exhaust_inventory` back into their pre-Workstream-3 behavior (no reservation
side effects). It does not touch existing `ReplenishmentReservation` rows or any `Order` already
created by a prior approval — an order that already exists went through the same, unmodified
full-payment flow as any other order and is unaffected by this flag in either direction. Rows left
in `pending_approval` when the flag is turned off simply stop being reachable through the customer
endpoints and stop being swept by the expiry job until the flag is re-enabled; they are not
deleted or corrupted.
