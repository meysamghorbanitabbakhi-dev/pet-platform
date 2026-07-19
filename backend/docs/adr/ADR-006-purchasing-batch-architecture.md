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
