# ADR-008 — Reserve-now architecture and why it ships live but gated

**Status:** Approved
**Date:** 2026-07-19

## Context

Workstream 2C asks for the reserve-now domain "full[y] built but `reserve_now_enabled=false` by
default": zero-charge reservation → explicit approval → full payment, with no invented deposit.
The settings flag itself already existed (`app/core/config.py`, wired through to
`GET /system/policies` since an earlier pass) with nothing behind it. This ADR is about what
"full domain" means concretely and how it avoids inventing product decisions the brief didn't
make.

## Decision

1. **Explicit offer mode, not inference.** `Offer.mode` (`full_payment` default | `reserve`) is
   operator-set, exactly like `sourcing_route` (ADR-006). An offer never becomes reservable by
   virtue of price, category, or any other attribute.
2. **Three-actor state machine, one row per attempt.** `Reservation`: `requested` (customer,
   zero charge) → `proposed` (operator reconfirms price/availability and proposes the — possibly
   changed — terms) → `converted` (customer approved; a real Order now exists) |
   `customer_declined` | `operator_declined` (the operator determines it isn't sourceable at all,
   skipping the customer entirely) | `expired`. `ReservationEvent` is the append-only state
   history the brief asks for separately from the record itself, mirroring
   `PurchaseBatchEvent`/`FulfillmentEvent`.
3. **The reconfirmed price is what gets charged, never the live offer price at approval time.**
   `reconfirmed_price_irr` is captured once, at proposal time, and is the only price
   `approve_and_convert_reservation` ever uses to build the resulting Order/OrderLine. Re-reading
   `offer.price_irr` at the moment the customer clicks approve — which could be minutes or days
   after reconfirmation — would silently undo the entire point of a reconfirmation step. Proven
   with a test that changes the live offer price *after* proposal and asserts the order still
   charges the reconfirmed number.
4. **Two independent deadlines, not one.** `operator_review_by` (set at request time) and
   `customer_respond_by` (set at proposal time, only once a proposal exists) are separate columns
   with separate scheduler sweeps, because they gate different actors and only one is ever active
   at a time. Both `approve_and_convert_reservation` and `decline_reservation` also self-check the
   deadline before acting (not only the sweep) — the same lazy-expiry pattern as Workstream 2E's
   shelf-life exceptions, for the same reason: a response that arrives after the deadline, whether
   because the sweep hasn't run yet or the request was merely in flight, must resolve to `expired`,
   never to a late `converted`/`customer_declined`.
5. **No deposit column exists anywhere in this schema.** The brief's "no invented deposit" is
   enforced structurally, not by convention: there is nothing to charge until
   `approve_and_convert_reservation` creates a normal `Order` in `awaiting_payment`, which then
   goes through the *existing, unmodified* `PaymentService`/Zarinpal flow for the full amount.
   `ReservationResponse.deposit_charged_irr` is a typed `Literal[0]` in the contract itself, the
   same idiom `OrderCancellationResponse.refund_auto_processed` and
   `ShelfLifeExceptionResponse.refund_auto_processed` already use to make a non-claim
   machine-checkable rather than just documented.
6. **Ships live at the code level, reachable only behind `reserve_now_enabled`.** Every
   customer and operator endpoint checks the flag first (`409 reserve_now_disabled`, the same
   convention `care_journey_delivery_enabled`/`concierge_requests_enabled` already use) and the
   scheduler's expiry sweep is only registered when the flag is on. This is a genuine difference
   from Workstream 2E, which ships live and ungated: 2E's shelf-life exception right exists the
   moment an operator can hit the pre-existing hard block, with no unresolved product number
   behind it. Reserve-now has no equivalent existing trigger, and — like late-delivery credit
   (Workstream 2D) — nothing about "should this be visible" is decided by this engineering pass.
7. **No frontend UI.** Unlike Workstreams 2A/2B/2E, whose customer endpoints are live the moment
   they ship, every reserve-now endpoint 409s while the flag is off. Building customer-facing UI
   against endpoints nobody can reach would be unverifiable and untestable in the running app —
   the same reasoning that kept Workstream 2D backend-only. UI is deferred to whichever future
   pass turns the flag on.

## Consequences

- `approve_and_convert_reservation` bypasses `CheckoutService.create_order` entirely rather than
  calling it with a one-item cart, specifically because that service always prices at the live
  `offer.price_irr` — reusing it would have reintroduced the exact bug point 3 above rules out.
  The two order-creation paths necessarily duplicate a few fields (address snapshot shape, outbox
  event); this is accepted rather than forcing a shared helper whose only two callers commit-price
  differently.
- Multiple reservation *attempts* per customer/offer are allowed (no uniqueness beyond the
  idempotency key) — a customer whose first reservation expired or was declined can request again.
  This differs from Workstream 2B/2E's one-record-per-order-or-line constraints, which model a
  single financial fact rather than a repeatable request.
- Declining or letting a reservation expire has no refund path to build: zero money ever moved.
  This is the one place in Workstream 2 where "no invented deposit" removes an entire category of
  work (refund attestation, wallet interaction) that 2B and 2E both needed.
