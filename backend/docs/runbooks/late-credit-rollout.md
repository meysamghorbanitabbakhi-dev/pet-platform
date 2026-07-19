# Late-delivery credit rollout runbook

`late_credit_enabled` and `late_credit_customer_visible` are separate flags (`app/core/config.py`),
both `false` by default per ADR-004. Enabling them is a founder/product decision, not an
engineering one — this runbook only covers how to enable them *safely* once that approval exists.

## What each flag actually gates

- `late_credit_enabled=true`: the scheduler's `_run_overdue_credit_job` (`app/workers/scheduler.py`)
  starts calling `process_overdue_orders` (`app/modules/wallet/jobs.py`) on its normal poll
  interval, which grants a 5%-of-merchandise wallet credit (`grant_late_delivery_credit`,
  `app/modules/wallet/service.py`) to every paid, non-cancelled/failed order whose
  `delivery_commitment_at` has passed and which has not already been credited. This is the
  *money-moving* flag.
- `late_credit_customer_visible=true`: the outbox handler for `wallet.late_delivery_credit_granted`
  (`enqueue_wallet_credit_notification`, wired in `app/workers/outbox.py`) starts actually creating
  in-app + SMS `Notification` rows instead of silently doing nothing. This is the *disclosure*
  flag. The credit can exist (`late_credit_enabled=true`) while still being invisible to the
  customer (`late_credit_customer_visible=false`) — useful for a silent dry run.

Both flags are also read into `PolicyResponse`/`GET /api/v1/system/policies` (`late_credit_enabled`
governs whether the operator UI/API surfaces late-credit tooling at all as far as the frontend is
concerned; `late_credit_customer_visible` is what the frontend's own `OrderPolicyFieldsResponse`
uses to decide whether to render wallet-credit UI, per `G5-ACC-06`/`G5-ACC-07` in the design-state
matrix).

## Pre-enablement checklist

1. **Founder/product approval recorded.** This runbook does not substitute for that approval; it
   assumes Decision 0.16-0.20 in the product decision record already covers the 5%/3-month terms,
   and that nothing about the *current* implementation (see "What's actually implemented" below)
   contradicts what was approved.
2. **Test evidence exists.** `pytest tests/integration/test_late_delivery_credit.py` passes against
   a real PostgreSQL instance (`K10_RUNTIME_TESTS=1`). This covers: on-time exclusion,
   overdue-undelivered, overdue-but-delivered-late, failed/cancelled exclusion, exactly-once
   creation under direct replay and real concurrency (`asyncio.gather` of 8 concurrent grant
   attempts against the same order), FIFO debit (single-credit and multi-credit-spanning cases),
   debit idempotency, insufficient-balance rejection, expired-credit exclusion, notification
   creation/suppression/preference-respecting/idempotency, and the full outbox-dispatcher path.
3. **Wallet balance is customer-visible somewhere before turning on notifications.** Confirm
   `GET /api/v1/pet-life/households/{household_id}/wallet` (already implemented, `G5-ACC-07`) is
   reachable from `/account` before setting `late_credit_customer_visible=true` — otherwise a
   customer gets an SMS about a credit they cannot see or spend anywhere in the product.
4. **SMS template exists and is active.** `enqueue_wallet_credit_notification` only *queues* the
   SMS `Notification` row; `deliver_pending_sms` (`app/modules/notifications/service.py`, already
   running on every scheduler tick regardless of these flags) requires an **active**
   `NotificationTemplate` row for `event_key="wallet.late_delivery_credit_granted"`,
   `channel="sms"` or delivery fails closed (`recipient_or_template_missing`, permanent failure,
   no retry). Confirm one exists and is approved copy before flipping
   `late_credit_customer_visible`.
5. **Decide the rollout order.** Recommended: enable `late_credit_enabled` alone first (credits
   accrue silently), let it run for a full delivery-commitment cycle (366h+) so any anomaly can be
   caught in the operator-only `GET /operator/...` tooling and `OperatorAuditLog`/outbox
   dead-letter queue before any customer sees a notification, *then* enable
   `late_credit_customer_visible`.

## What's actually implemented today (do not assume more than this)

- The scheduler job and wallet service are real and tested (see above). The operator can also
  trigger a single order's credit manually via `POST /operator/orders/{order_id}/late-credit`
  (audited).
- Wallet balance read: `GET /api/v1/pet-life/households/{household_id}/wallet`.
- SMS quiet-hours and per-event opt-out are respected (`NotificationPreference`); there is no
  customer-facing UI for granular late-credit-only notification content beyond the existing
  generic SMS preference toggle.
- There is **no dedicated launch-day dashboard** for late-credit volume/exceptions. Use
  `GET /operator/...` OperatorAuditLog queries (`action = 'wallet.late_delivery_credit'` for
  manual grants) and the outbox dead-letter count for now; a KPI view is out of scope for this
  runbook (see Workstream 6).

## Enabling

1. Set `LATE_CREDIT_ENABLED=true` in the deployment secret manager. Restart the scheduler process
   only (API/worker do not need a restart for this flag; `_run_overdue_credit_job` reads
   `get_settings()` fresh each tick, but `Settings` is process-cached — a full scheduler restart
   is the safe way to pick up the change).
2. Watch the scheduler logs for `created %s overdue-order wallet credits` on the next few polls.
   Cross-check against `SELECT count(*) FROM wallet_credits WHERE source_type = 'late_delivery'`.
3. After a full delivery-commitment cycle with no anomalies, set
   `LATE_CREDIT_CUSTOMER_VISIBLE=true` and restart the outbox worker process (same caching
   consideration as step 1).
4. Watch `notifications_notifications` for `event_key = 'wallet.late_delivery_credit_granted'`
   rows moving from `queued` to `sent`, and the outbox dead-letter count
   (`OutboxEvent.status = 'dead_letter'`) for zero growth.

## Rollback

Both flags can be turned back to `false` independently at any time; neither flag deletes or
reverses already-granted wallet credit (by design — a credit already granted is a real customer
entitlement). Turning `late_credit_enabled` off only stops *new* credits from being granted; it
does not affect FIFO debit of existing balances, which is unconditional.
