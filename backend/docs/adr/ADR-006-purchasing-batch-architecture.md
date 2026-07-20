# ADR-006 — Purchasing batch architecture and threshold fallback

**Status:** Approved
**Date:** 2026-07-19

## Context

Workstream 2A asks for purchase batches (Decision 0.10-0.13), gated behind founder-confirmed
answers on three points that were not otherwise specified: which offers pool into aggregated
batches, what unit the minimum-viable threshold is measured in, and how batches relate to the
existing `Order`/`SourcingJob` model. Decision 0.17's internal loss-ceiling number itself remains
explicitly deferred (product decision record, Part XXI) and is not decided by this ADR.

## Decision

1. **Route selection**: `Offer.sourcing_route` (`aggregated` default | `individual`) is an
   explicit, operator-set field. Never inferred from price, category, or any other product
   attribute.
2. **Threshold unit**: total allocated quantity (units), operator-configurable per batch via
   `PurchaseBatch.minimum_viable_threshold_quantity`. The specific numeric value is never
   hardcoded by this engineering pass — it is always operator data, consistent with Decision
   0.17 leaving the actual loss-ceiling number to a later, non-engineering decision.
3. **Architecture — commitment lives on the batch, every order line gets one**:
   `PurchaseBatch` groups `OrderLine`s (via `PurchaseBatchAllocation`, one row per order line,
   unique on `order_line_id`) for one offer. `aggregated`-route offers pool into the current open
   batch for that offer (created lazily, 7-day rolling deadline from first allocation, not a
   fixed calendar weekday — nothing in the decision record specifies a weekday/timezone
   convention, and inventing one would be exactly the kind of silent assumption this program's
   own governance forbids). `individual`-route offers always get a dedicated, single-line batch
   (Decision 0.10: exceptional/high-value items are sourced one at a time, never pooled with
   another customer's order for the same rare offer, regardless of whether two customers happen
   to want the same one). This means **every** order line always has exactly one batch
   allocation — Workstream 2B's cancellation-eligibility check has one code path, not two.
   `SourcingJob` (existing, 1:1 with `Order`) is untouched by this decision; it continues to
   track the order-level sourcing *process* status, a separate, coarser concept from per-line
   supplier commitment.
4. **Threshold-reached vs. committed are different facts**: `threshold_reached_at` is a
   system-computed timestamp (set the moment cumulative allocated quantity crosses the
   configured threshold) that only enables *earlier* sourcing (Decision 0.11) — it is an
   optimization signal, not a gate. `committed_at` (+ `committed_by_operator_id` +
   `commitment_evidence_file_id`) is always an explicit, evidenced operator action recording
   that money actually left the platform toward a supplier. A batch reaching its threshold, or
   its deadline passing, never auto-commits — per Decision 0.12, the platform proceeds even when
   a threshold is missed, so nothing about deadline/threshold should force an early, unevidenced
   commitment either.
5. **No configured threshold fallback**: if an `aggregated` batch is auto-opened for an offer
   with no operator-configured `Offer.default_batch_threshold_quantity`, the batch's threshold
   falls back to `1` — i.e., "no real aggregation benefit occurs," which is the truthful
   consequence of nobody having configured a real number, not a guessed value dressed up as a
   deliberate one. This keeps checkout/payment-verify from ever blocking on missing batch
   configuration while never fabricating an economically meaningful threshold.

## Consequences

- Batch-level cancellation (an operator abandoning an entire batch, as opposed to a customer
  cancelling their own order before commitment) is out of scope for this pass. Decision 0.12's
  "must not silently cancel paid orders" makes whole-batch cancellation an exceptional,
  carefully-reasoned operator action, not a routine one; building it prematurely risks exactly
  the kind of unreviewed cancellation behavior the decision record warns against. A future ADR
  should cover it if/when a real operational need arises.
- A scheduler job that auto-transitions batches on deadline is deliberately not built:
  `deadline_at` is customer-visible/informational (Decision 0.11's "visible weekly deadline") and
  an operator-review signal, not an automation trigger, since commitment always requires a human
  evidence-bearing action per point 4 above.

## Amendment (2026-07-20) — gap-closure program, Workstream 6

The gap-closure mission brief flagged three items against this ADR. Each is addressed below;
none required inventing an unspecified business number.

1. **Fixed weekly cutoff vs. rolling deadline (point 3, "not a fixed calendar weekday")** — the
   brief asked for a fixed weekday/timezone cutoff. This ADR's original reasoning was that no
   decision record specifies which weekday or timezone convention to use, and guessing one would
   itself be the silent-assumption failure this program's governance forbids. Asked directly,
   the product owner confirmed: **keep the rolling 7-day-from-first-allocation deadline** — point
   3 stands unchanged. This is recorded as the resolution, not a default assumption.
2. **"Unsafe effective fallback threshold of one" (point 5)** — **superseded.** An `aggregated`
   offer with no operator-configured `default_batch_threshold_quantity` no longer silently opens
   a batch with a threshold of 1 (which gave "aggregation" no real pooling effect and could let a
   single order look commit-ready). `PATCH /offers/{id}/sourcing-config` now rejects setting
   `sourcing_route="aggregated"` without a threshold (422), and
   `purchasing.service._find_or_open_batch` now raises `PurchasingError` defensively if it ever
   encounters that state anyway (pre-existing rows, direct DB writes). Payment verification and
   reconciliation both catch this as a distinct 500 (`purchase_batch_configuration_error`) rather
   than crashing uncontrolled or silently mis-pooling — an operator-fixable configuration error,
   not a customer error; nothing commits, so retry succeeds once the offer is configured. This
   does not guess an economically meaningful number; it just requires the number this ADR always
   said should be operator data, before rather than after the batch depends on it.
3. **Deadline enforcement was considered and reverted** — investigating point 2 surfaced that
   `_find_or_open_batch` reuses the current open batch for new allocations even after its
   `deadline_at` has passed, so the "visible weekly deadline" (Decision 0.11) has no effect on
   new demand by itself. An attempt to stop reusing an expired-but-open batch was implemented and
   then reverted after its own test caught a real conflict: `uq_purchasing_batches_one_open_aggregated_per_offer`
   enforces at most one `open` aggregated batch per offer at the database level, and there is no
   batch status between `open` and `committed`/`cancelled` for a deadline to transition a batch
   into — so a second, fresh batch cannot coexist with the first while it stays `open` awaiting
   operator review. Re-reading this ADR's own point above (`deadline_at` is "customer-visible/
   informational ... an operator-review signal, not an automation trigger") confirms this was the
   correct original design, not an oversight: making the deadline gate new pooling is a real
   feature that needs its own schema change (e.g. a `closed` status) and its own ADR, not a
   drive-by fix bundled into this one. Left unchanged; guarded by
   `test_a_batch_past_its_deadline_still_absorbs_new_allocations`.
4. **Whole-batch cancellation ("out of scope ... future ADR")** — the gap-closure brief is that
   future operational need. Implemented conservatively: `purchasing.service.cancel_batch` (via
   `POST /operator/purchase-batches/{id}/cancel`) only cancels a batch with zero active
   (un-voided) allocations. It does not bulk-detach or cancel any live paid order — Decision
   0.12's constraint is preserved by construction, not by a runtime check. Cancelling a batch that
   still holds live orders requires cancelling those orders individually first (the existing
   customer-cancellation path already voids each one's allocation as it goes). A batch that
   reaches zero allocations that way, or was opened but never allocated into, can now be marked
   cancelled instead of sitting `open` forever with no path to resolution.
