# Reserve-now rollout runbook

`reserve_now_enabled` (`app/core/config.py`) is `false` by default. Enabling it is a
founder/product decision — which offers should be reservable, and what the operator review SLA
actually is in practice — not an engineering one. This runbook only covers how to enable the
already-built domain safely once that approval exists. See ADR-008 for the architecture.

## What the flag actually gates

`reserve_now_enabled=true` makes every reserve-now endpoint reachable instead of returning
`409 reserve_now_disabled`:

- Customer: `POST /api/v1/reservations`, `GET /api/v1/reservations`,
  `GET /api/v1/reservations/{id}`, `POST /api/v1/reservations/{id}/approve`,
  `POST /api/v1/reservations/{id}/decline`.
- Operator: `POST /api/v1/operator/reservations/{id}/reconfirm-and-propose`,
  `POST /api/v1/operator/reservations/{id}/decline`, `GET /api/v1/operator/reservations`,
  `GET /api/v1/operator/reservations/{id}`.
- The scheduler's `_run_reservation_expiry_job` (`app/workers/scheduler.py`), which is not even
  *registered* while the flag is off — there is nothing for it to expire, since
  `POST /reservations` itself 409s.

There is no separate "customer visible" flag the way late-delivery credit (Workstream 2D) has
one: reserve-now's customer-facing surface and its underlying capability are the same flag,
because unlike a wallet credit there is nothing to grant silently — a reservation only exists
because a customer made one through the endpoint the flag gates.

## Pre-enablement checklist

1. **Founder/product approval recorded**, specifically covering: which offers become
   `mode='reserve'` (this is an explicit, operator-set field per offer — turning the global flag
   on does not itself make anything reservable), the operator review SLA (`operator_review_by`
   defaults to 48h from request, `reconfirm_and_propose_reservation`'s
   `review_window_hours` parameter), and the customer response SLA (`customer_respond_by`,
   defaults to 48h from proposal, `response_window_hours` parameter). Both defaults are
   engineering placeholders, not approved numbers.
2. **Test evidence exists.** `pytest tests/integration/test_reservations.py` passes against a
   real PostgreSQL instance (`K10_RUNTIME_TESTS=1`). This covers: zero-charge request, rejection
   of non-`reserve`-mode offers, request idempotency, reconfirm-and-propose idempotency, operator
   decline (before and after proposal), customer decline and its idempotency, conversion at the
   *reconfirmed* price even when the live offer price has since changed again, approval
   idempotency (returns the same order, never a second one), address-ownership rejection, both
   expiry deadlines (self-check on late response and the scheduler sweep), the
   approve-vs-decline concurrency race, and non-enumerating access to another customer's
   reservation.
3. **No frontend UI exists yet** (see ADR-008, point 7) — building it is required before this can
   actually launch to customers, regardless of the flag. This runbook covers the backend only.
4. **Notification template exists and is active** for `event_key="reservations.proposed"`,
   `channel="sms"`, the same `deliver_pending_sms` fail-closed requirement as every other
   templated notification in this codebase (`recipient_or_template_missing` otherwise, permanent
   failure, no retry).
5. **Offers are flagged `mode='reserve'` deliberately**, via
   `PATCH /operator/offers/{offer_id}/sourcing-config`... no — reserve mode is not on that
   endpoint; it is set directly on the `Offer` row (no dedicated operator endpoint exists yet to
   toggle `Offer.mode` at runtime, since no reservable offers existed to manage before this
   workstream). Add one before launch if operators need to self-serve this instead of a one-off
   data change.

## Enabling

1. Set `RESERVE_NOW_ENABLED=true` in the deployment secret manager. Restart the API process (for
   the customer/operator endpoints) and the scheduler process (to register
   `_run_reservation_expiry_job`) — `Settings` is process-cached, so a restart is the safe way to
   pick up the change everywhere.
2. Confirm at least one real offer has `mode='reserve'` — otherwise every request will
   legitimately 409 with `offer_is_not_reservable`, which will look like a bug but isn't one.
3. Watch scheduler logs for `expired stale reservations: {...}` and cross-check against
   `SELECT status, count(*) FROM reservations_reservations GROUP BY status`.
4. Watch `OperatorAuditLog` for `reservation.reconfirmed_and_proposed` /
   `reservation.operator_declined` entries to confirm operators are actually reviewing requests
   within the approved SLA, not letting them silently expire.

## Rollback

Turning `reserve_now_enabled` back to `false` immediately 409s every reserve-now endpoint again
and de-registers the expiry sweep. It does not touch existing `Reservation` rows or any `Order`
already created by a prior approval+conversion — an order that already exists went through the
same, unmodified full-payment flow as any other order and is unaffected by this flag in either
direction.
