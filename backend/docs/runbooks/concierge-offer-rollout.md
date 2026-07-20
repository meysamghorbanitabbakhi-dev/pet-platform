# Concierge offer rollout runbook

`concierge_offers_enabled` (`app/core/config.py`) is `false` by default. Enabling it is a
founder/product decision about operational readiness (do operators exist who can actually verify
authenticity, source, and landed price for unlisted-product requests?), not an engineering one —
the underlying domain (review, presentation, acceptance, decline, expiry, refresh, promotion) is
already built and tested. See ADR-010 for the architecture and
`pet_platform_product_decision_record.md` Part XII (Decisions 0.33-0.37) for the locked product
rules this implements. This runbook only covers how to enable the already-built domain safely once
approval exists.

Note this is a *different* flag from `concierge_requests_enabled` (already `true` by default):
customers can already submit `concierge_sourcing` requests today. This flag gates only the
verified-offer machinery layered on top — while it is off, those requests simply sit unactioned
through this pipeline (an operator can still resolve them manually outside the system, as before
this workstream).

## What the flag actually gates

`concierge_offers_enabled=true` makes every concierge-offer endpoint reachable instead of
returning `409 concierge_offers_disabled`:

- Customer: `GET /api/v1/customer-requests/{request_id}/concierge-offers`,
  `GET /api/v1/concierge-offers/{id}`, `POST /api/v1/concierge-offers/{id}/accept`,
  `POST /api/v1/concierge-offers/{id}/decline`, `POST /api/v1/concierge-offers/{id}/refresh`.
- Operator: `POST /api/v1/operator/customer-requests/{request_id}/concierge-offers/start-review`,
  `POST /api/v1/operator/concierge-offers/{id}/present`,
  `POST /api/v1/operator/concierge-offers/{id}/unavailable`,
  `POST /api/v1/operator/concierge-offers/{id}/promote`,
  `GET /api/v1/operator/concierge-offers`, `GET /api/v1/operator/concierge-offers/{id}`.
- The scheduler's `_run_concierge_offer_expiry_job` (`app/workers/scheduler.py`), which is not even
  *registered* while the flag is off.
- Frontend: the concierge-offer section on `src/features/support/concierge-request-detail.tsx`
  (`/support/{request_id}`) renders nothing while `shouldRenderConciergeOffers(policy)` is false.

## Pre-enablement checklist

1. **Founder/product approval recorded**, specifically covering: the default validity window
   (`concierge_offer_default_validity_hours`, default 24h, matches Decision 0.35's default
   exactly — confirm this is still the intended figure, and that operators understand they may
   choose anywhere from 12-48h per offer based on source reliability/price volatility, not just
   accept the default reflexively), and confirmation that promotion to the public catalog
   (`POST .../promote`) is understood as fully operator-discretionary with no automatic trigger —
   see ADR-010 point 7.
2. **Operators exist who can actually perform verification.** This is the real gate: the system
   enforces that `present_offer` requires a `verification_evidence_file_id` (uploaded via the
   existing `POST /operator/evidence-files`) and a `supplier_id` referencing a real
   `catalog_suppliers` row, but it cannot verify the *content* of that evidence — the operational
   process for actually confirming authenticity/landed price/delivery feasibility before
   presenting an offer is outside this system's scope and must exist before launch.
3. **Test evidence exists.** `pytest tests/integration/test_concierge_offers.py` passes against a
   real PostgreSQL instance (`K10_RUNTIME_TESTS=1`, 32 tests). This covers: the full state machine
   (start-review idempotency, both pricing modes' required-field validation, validity-hours
   bounds, presented-offer immutability, unavailable, accept creating a real order with zero
   `PaymentAttempt` rows, accept/decline idempotency, accept-after-expiry, refresh creating a new
   cycle without touching the expired row, refresh idempotency while a cycle is active, the expiry
   sweep, catalog promotion and its cap-lifting, a concurrent accept-vs-decline race, HTTP gating,
   the full HTTP lifecycle including the customer-vs-operator response shape difference,
   non-enumerating 404s, operator queue status filtering, and that an accepted offer's one-off
   catalog Offer is excluded from `/catalog/offers` and `/catalog/offers/search` but reachable by
   id). Frontend: `pnpm test` (`src/lib/policy.test.ts`,
   `src/features/support/concierge-request-detail.test.tsx`).
4. **Notification templates exist and are active** for `event_key="concierge.offer_presented"`,
   `"concierge.offer_unavailable"`, and `"concierge.offer_expired"`, `channel="sms"` — the same
   `deliver_pending_sms` fail-closed requirement as every other templated notification in this
   codebase. None is seeded today (matching the same pre-existing, not-yet-closed gap noted for
   Workstream 3's notifications); the in-app channel works regardless, only SMS delivery is
   affected. All three deep-link to `/support/{request_id}` via the existing
   `destination_kind='customer_request'` notification mapping — no frontend routing change is
   needed to wire this up.

## Enabling

1. Set `CONCIERGE_OFFERS_ENABLED=true` (and, if the approved default differs,
   `CONCIERGE_OFFER_DEFAULT_VALIDITY_HOURS`) in the deployment secret manager. Restart the API
   process (customer/operator endpoints) and the scheduler process (to register the expiry job) —
   `Settings` is process-cached, so a restart is the safe way to pick up the change everywhere.
2. Confirm at least one operator account exists with `identity_type='operator'` and knows the
   `start-review` → `present`/`unavailable` workflow.
3. Watch scheduler logs for `expired N stale concierge offers`, cross-checked against
   `SELECT status, count(*) FROM concierge_offers GROUP BY status`.
4. Watch for `concierge.offer_presented` / `concierge.offer_unavailable` / `concierge.offer_expired`
   outbox events dispatching successfully (`system_outbox_events` dead-letter count should stay at
   zero for these event types).
5. Spot-check that an accepted offer's resulting `Order` reaches `awaiting_payment` and the
   customer completes payment through the existing, unmodified Zarinpal flow — no code path in
   this workstream auto-charges anything.

## Rollback

Turning `concierge_offers_enabled` back to `false` immediately 409s every concierge-offer endpoint
again and de-registers the expiry sweep. It does not touch existing `ConciergeOffer` rows, any
`Order` already created by a prior acceptance, or any `Offer`/`Product` already promoted to the
public catalog — an order or a promoted catalog offer that already exists is unaffected by this
flag in either direction, since both went through the same, unmodified downstream machinery as any
other order/offer. Rows left in `reviewing`/`offer_presented`/`refresh_requested` when the flag is
turned off simply stop being reachable through the customer/operator endpoints and stop being swept
by the expiry job until the flag is re-enabled; they are not deleted or corrupted.
