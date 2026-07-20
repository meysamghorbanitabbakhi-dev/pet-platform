# ADR-010 — Verified concierge offer architecture and why it lazily promotes into the catalog

**Status:** Approved
**Date:** 2026-07-20

## Context

Workstream 4 extends the existing `support_customer_requests` queue (`request_type=
'concierge_sourcing'`) into an auditable, verified-offer lifecycle: an operator reviews an
unlisted-product request, verifies authenticity/source/landed price/delivery feasibility, and
presents a payable offer the customer explicitly accepts or declines. This is a locked product
decision (`pet_platform_product_decision_record.md`, Part XII, Decisions 0.33-0.37): no payment
before an offer is verified and presented; hybrid pricing (reference-price savings when a reliable
market reference exists, otherwise transparent landed-cost-plus-margin); 12-48h validity (default
24h) with the price locked for that window; no automatic re-verification after expiry, only a
customer-initiated refresh; and catalog promotion only at platform discretion after validating
demand, sourcing reliability, economics, compliance, and delivery performance. This ADR is about
how that decision is implemented on top of the pre-existing request queue, and why acceptance
lazily creates a normal catalog `Offer` rather than a parallel order-creation path.

## Decision

1. **Two-layer model: the request queue stays the anchor, `ConciergeOffer` is the lifecycle on
   top.** `CustomerRequest` (unchanged) is still where a request is submitted and where its
   coarse `submitted/in_review/resolved/closed` status lives. `ConciergeOffer` is a new,
   separate table FK'd to it, one row per *offer cycle* — a request can have several over time
   (see point 5), but the request itself is never duplicated or forked.
2. **Status set mirrors the brief's simplified path plus the product decision record's explicit
   `Refresh requested` state**: `reviewing` → `offer_presented` → `accepted` | `declined` |
   `expired`, plus `unavailable` (operator determines it cannot be sourced at all, mirroring
   reserve-now's `operator_declined`) and `refresh_requested` (an alternate entry status,
   parallel to a fresh cycle's `reviewing`, used only for a cycle created by a customer's refresh
   request). The product decision record's own state lists (§39 and §53) additionally spell out
   `Source under verification`/`Source verified`/`Verification in progress` as separate
   sub-phases of what this implementation treats as one `reviewing` status, and `Converted to
   order` as separate from `Accepted` — both intentional simplifications: the sub-phases are
   internal operator workflow, not a customer-visible distinction worth a state transition, and
   acceptance creates the Order in the same call (point 4), so there is nothing for a customer to
   observe between "accepted" and "an order exists."
3. **Hybrid pricing is two mutually exclusive modes, never both.** `pricing_mode` is
   `reference_price_savings` (requires `reference_price_irr`) or `landed_cost_plus_margin`
   (requires at minimum `supplier_cost_irr` and `platform_margin_irr` of the nine tracked
   components — supplier cost, exchange-rate basis, international transport, customs/clearance,
   handling, domestic delivery, payment fees, risk reserve, platform margin). `present_offer`
   validates the required fields for whichever mode is chosen before allowing the transition.
4. **Acceptance reuses `CheckoutService.create_order` via a lazily-created, hidden one-off
   `Offer`, never a parallel order-creation path.** `OrderLine.offer_id` is a required FK — there
   is no way to create a real, deliverable order without a real `Offer` row, and the requested
   product is by definition not already in the catalog (Decision 0.33's title is "Unlisted
   Product Requests"). Rather than requiring an operator to manage a `Product`/`Offer` pair
   up front for every request — most of which are one-off and never repeat, per Decision 0.37's
   own promotion criteria being about *recurring* demand — `accept_offer` creates a minimal
   `Product` and an `Offer(mode='concierge_only', sourcing_route='individual',
   max_pending_quantity=quantity)` at the moment of acceptance, from the fields already captured
   on the `ConciergeOffer` at presentation time. `mode='concierge_only'` is excluded from
   `/catalog/offers` and `/catalog/offers/search` (a one-line addition to the existing
   `_offer_availability_filters` helper both endpoints already share) but remains reachable by id
   — exactly the shape the resulting order and its `OrderLine` snapshot need, with zero special
   casing anywhere else in the order/payment/sourcing/delivery pipeline.
5. **A refresh always opens a new cycle; the old row's fields are never touched again.**
   `request_refresh` requires the offer being refreshed to be `expired`, and creates a new
   `ConciergeOffer(status='refresh_requested', refreshed_from_offer_id=<old id>)` rather than
   resetting the old row. This is Decision 0.36 read literally: "old offer is never silently
   reactivated." It also means `ConciergeOffer.request_id` is deliberately *not* unique — unlike
   Workstream 3's replenishment reservations (one row per inventory unit, ever, because a unit
   has exactly one need window), a concierge request can legitimately cycle through several offer
   attempts, each a complete, immutable historical record once terminal.
6. **Operator-only fields are a structurally separate response type, not a filtered field list on
   one type.** `ConciergeOfferResponse` (customer) and `ConciergeOfferOperatorResponse` (operator)
   are two distinct Pydantic models in `app/api/contracts.py`. The customer response has no
   `supplier_id` field at all (only `supplier_country_code`, resolved via a join at response-build
   time, the same country-not-identity precedent `OfferDetailResponse` already sets) and none of
   the nine landed-cost columns — this is enforced by the type itself, not by a runtime redaction
   step that could be forgotten on a future field addition.
7. **Catalog promotion is an operator-attested decision, not a computed score.** The product
   decision record's ten promotion criteria (request frequency, conversion, repeat demand, source
   stability, authenticity confidence, landed margin, delivery performance, product documentation,
   customer feedback, operational complexity) are inherently qualitative judgment calls, several of
   which this system cannot mechanically compute (customer feedback, compliance). `promote_to_catalog`
   requires a free-text `rationale` or the same evidence-file-and-reason discipline this codebase
   already uses for supplier assurances and shelf-life exceptions, rather than fabricating an
   automatic threshold-based score. It flips the lazily-created `Offer.mode` from
   `'concierge_only'` to `'full_payment'`, clears the one-off `max_pending_quantity` cap, and
   resets `sourcing_route` to `'aggregated'` (the normal catalog default, ADR-006) — the same row
   that fulfilled the first order becomes the real catalog offer, not a freshly created one, so
   promotion carries zero data-migration risk.
8. **Ships live at the code level, reachable only behind `concierge_offers_enabled`.** Every
   endpoint checks the flag first (`409 concierge_offers_disabled`), the scheduler's expiry sweep
   is only registered when the flag is on, and the frontend gates the offer section on the
   existing `/support/{request_id}` page on the same flag — same convention as
   `replenishment_reservation_enabled` (ADR-009). Unlike `concierge_requests_enabled` (already
   live, true by default — customers can submit a request today), this flag gates only the
   *verified-offer* machinery layered on top; a disabled flag does not stop customers from
   submitting `concierge_sourcing` requests, it only 409s the offer-specific endpoints.

## Consequences

- Customer access checks compare `ConciergeOffer.customer_identity_id` directly (denormalized
  from the parent request at cycle-creation time), the same direct-ownership shape
  `CustomerRequest.identity_id` itself already uses — simpler than Workstream 3's
  household-membership check, since this resource is identity-owned, not shared household
  inventory.
- No deposit column exists anywhere in this schema, the same structural argument ADR-008/ADR-009
  make: there is nothing to charge until `accept_offer` creates a normal `Order` in
  `awaiting_payment`, which then goes through the unmodified `PaymentService`/Zarinpal flow.
  `ConciergeOfferResponse.auto_charged` is a typed `Literal[False]`, matching the established
  idiom.
- `present_offer` is idempotent and immutable once an offer reaches `offer_presented` — a second
  call with different facts is silently ignored, returning the original. There is deliberately no
  "operator withdraws/revises a presented offer" capability; Decision 0.35's "price locked during
  validity" treats a presented offer as stable by design, and an operator mistake is expected to
  either be caught before presenting or left to expire naturally. This is a known, accepted gap,
  not an oversight — adding a withdrawal path is future scope if it proves necessary in practice.
- The scheduler's expiry sweep and the shared-test-database interaction it has with
  `catalog_offers.mode`'s CHECK constraint (a later migration narrowing an earlier one's allowed
  values will correctly fail closed if any row still uses the value being removed) means test
  suites that create `mode='concierge_only'` rows must neutralize them before any test exercises a
  full downgrade past this migration — see `tests/integration/test_concierge_offers.py`'s
  module-scoped cleanup fixture.
