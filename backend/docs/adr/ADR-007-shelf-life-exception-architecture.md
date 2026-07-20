# ADR-007 — Shelf-life exception architecture and refund attestation reuse

**Status:** Approved
**Date:** 2026-07-19

## Context

Workstream 2E asks for an operator-proposed exception to the existing shelf-life hard block
(`confirm_sourced_unit` in `app/api/routes/operator.py`, unchanged by this ADR), with explicit
customer accept/decline, a repricing/snapshot record, no fulfillment until accepted, and a full
refund path when declined or the exception goes unanswered. The refund mechanism itself was
already decided during Workstream 2B's clarifying questions: operator-attested manual refund, not
an automatic payment-gateway reversal — and that question was explicitly framed to cover *both*
2B's order cancellation and 2E's declined/expired exceptions, not two independent decisions.

## Decision

1. **The exception record *is* the repricing/snapshot record.** `ShelfLifeException` carries
   `proposed_exact_expiry_date` and `additional_discount_irr` at proposal time, and the same row
   is updated in place on response — there is no separate snapshot table. A dedicated snapshot
   table would only be justified if the proposal could be revised or re-proposed after the fact;
   it cannot (`one_exception_per_order_line`), so the row's own history (`proposed_at`,
   `responded_at`, `status`) already is the full record.
2. **No fulfillment until accepted is enforced by construction, not a new check.**
   `project_delivered_order` already requires `SourcedUnitEvidence` for every order line before
   materializing inventory. Accepting an exception is the only path that creates that evidence for
   a line with a proposed exception (`authenticity_basis='shelf_life_exception_accepted'`,
   distinguishable from the normal `'supplier_verified'` path); declining or expiring never does.
   No additional gate was added — reusing the existing constraint is more honest than duplicating
   it.
3. **Declining one line must not block the rest of a multi-line order's delivery.**
   `project_delivered_order`'s original loop raised on the *first* line missing evidence,
   regardless of the other lines' state. A declined/expired exception can never produce evidence
   (the customer refused it), so without a change here a single problematic line would permanently
   block delivery of an order's unrelated, perfectly fine lines. `OrderLine.excluded_from_delivery_at`
   (set by decline and by the expiry sweep, never by accept) makes the projection skip that line
   instead. This is a real, if narrow, change to shared checkout/fulfillment code — not something
   2E could avoid by staying self-contained.
4. **Refund attestation is a shared, structural (not inherited) mechanism.**
   `app/modules/orders/refund_attestation.py` defines a `Protocol` (`refund_status`,
   `refund_attested_at`, `refund_attested_by_operator_id`, `refund_evidence_file_id`,
   `refund_reference`) and one `attest_refund()` function. `OrderCancellation` (2B) and
   `ShelfLifeException` (2E) each declare their own matching columns and are used through this
   function structurally — no shared base table, no polymorphic FK. The two entities are genuinely
   different facts (whole-order voluntary cancellation vs. line-level involuntary shelf-life
   failure, with different snapshots and different eligibility rules); forcing them into one table
   would trade a few duplicated columns for a much worse "applies only in this case" schema. 2B's
   own operator attestation endpoint (`POST /operator/order-cancellations/{id}/attest-refund`) was
   missing until this pass added it alongside 2E's — closing that gap here, using the same
   mechanism, was more honest than leaving `OrderCancellation.refund_status` a permanent dead end.
5. **A late response expires instead of silently succeeding.** Both `accept_shelf_life_exception`
   and `decline_shelf_life_exception` check the deadline themselves before acting (not only the
   scheduler sweep), so a customer's response that arrives after `respond_by` — whether because the
   sweep hasn't run yet or the request was merely in flight — always resolves to `expired`, never
   to a late `accepted`/`declined`. `expired` carries the same full-refund consequence as decline;
   the distinction is honesty about what happened, not a different outcome.
6. **This capability ships live, not behind a settings flag**, unlike reserve-now (Workstream 2C)
   or late-delivery credit (Workstream 2D). Nothing in the 2E brief asked for a disabled-by-default
   gate, and — unlike those two — there is no unresolved product/business number this depends on
   (no deposit percentage, no loss-ceiling threshold). The customer's accept/decline right exists
   the moment an operator can hit the existing hard block, so notification (`enqueue_shelf_life_exception_notification`)
   and the expiry sweep both run unconditionally too, matching Workstream 2A/2B's precedent.

## Consequences

- Committing to "the exception record is the snapshot" means a mistaken proposal (wrong discount,
  wrong date) cannot be corrected in place — an operator can only wait for the customer to decline
  it or its deadline to pass, then nothing else can be proposed for that line automatically (the
  line stays permanently excluded from delivery once declined/expired). A future workstream would
  need to add an explicit re-open/re-propose path if this turns out to matter operationally.
- `OrderLine.excluded_from_delivery_at` is a narrow, additive column with a single writer path;
  it does not model partial refunds, partial shipments, or any other line-exclusion reason beyond
  shelf-life decline/expiry. A future partial-fulfillment feature should not assume this field's
  meaning generalizes without re-checking every place that currently treats "excluded" and
  "declined/expired shelf-life exception" as synonymous.

## Amendment (2026-07-20) — gap-closure program, Workstream 7

Three items, all addressed without inventing an unspecified business number:

1. **Re-propose after decline/expiry** — the first Consequence above explicitly named this as a
   deferred future workstream; the gap-closure brief is that workstream. `one_exception_per_order_line`
   (migration 20260719_0032) is replaced by a partial unique index
   (`uq_shelf_life_exceptions_one_active_per_order_line`, migration 20260720_0038) that only
   applies while a row is still `'proposed'`. At most one *active* proposal per line at a time,
   exactly as before; a resolved (declined/expired) one no longer blocks a revised re-proposal.
   `'accepted'` stays excluded independently by `propose_shelf_life_exception`'s pre-existing
   `already_sourced` check. "The exception record is the snapshot" (point 1 above) still holds per
   proposal — a re-proposal is a new row with its own snapshot, not an edit to the old one.
2. **Positive-discount requirement** — `additional_discount_irr >= 0` allowed a $0-compensation
   exception: asking a customer to accept a product short of the guarantee they paid for with
   nothing in return. Tightened to `> 0` at three layers (Pydantic body, service function, DB
   CHECK constraint via the same migration) — not a judgment call this ADR made originally, just
   an unaddressed gap.
3. **No invented 72-hour deadline** — `_DEFAULT_RESPONSE_WINDOW_HOURS = 72` was a hardcoded Python
   module constant with no way to change it short of a code deploy. Moved to
   `settings.shelf_life_exception_response_window_hours` (default 72, bounds 1-168h, same pattern
   as `concierge_offer_default_validity_hours`) — operator-configurable now, still 72h out of the
   box so no behavior actually changes until someone deliberately reconfigures it.

Also fixed, found auditing fulfillment rather than this module directly: `project_delivered_order`
(`app/modules/inventory/projection.py`) now rejects marking an order delivered if any line's
confirmed `SourcedUnitEvidence.exact_expiry_date` has already passed by delivery time. A
short-shelf-life exception's accepted date is fixed at acceptance time, potentially days before
actual delivery; slow fulfillment must not ship an already-expired unit just because the date was
valid when confirmed. Applies to every line, not only shelf-life-exception ones, since both share
the same `SourcedUnitEvidence` record.
