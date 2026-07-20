# ADR-012: Offer-mode checkout eligibility is enforced centrally, not implicitly

**Status:** Accepted (2026-07-20, gap-closure security pass)

## Context

A systematic audit against the gap-closure mission brief's Workstream 1 ("Central offer
eligibility and checkout authorization") found that `Offer.mode` (`full_payment` / `reserve` /
`concierge_only`) was never checked by the ordinary, customer-initiated checkout path
(`CheckoutService.create_order`), nor by two other places that select or surface offers for a
customer to act on:

- `app/api/routes/pet_life.py`'s `_reorder_options` (feeds the customer-facing reorder-assessment
  response).
- `app/modules/replenishment/reservations.py`'s `_find_available_offer` (the offer the scheduler
  auto-selects for a replenishment recommendation, which converts straight into a real order on
  approval).
- `app/api/routes/commerce.py`'s public, fully unauthenticated `GET /catalog/offers/{offer_id}`
  detail route.

A `reserve`- or `concierge_only`-mode offer reaches `status='active'`,
`stock_posture='sourced_after_payment'`, and `sourcing_capacity_status='open'` exactly like an
ordinary offer (confirmed by reading `app/modules/concierge/service.py`'s offer-creation code),
so none of the existing checks in these four places distinguished them. Concretely, this meant:

1. Any customer who learned an offer's id (a leaked link, a shared concierge-offer id, simple
   UUID guessing) could complete a real, full-payment purchase of a `reserve`-mode offer
   (bypassing the operator price/availability reconfirmation workflow entirely) or of a
   `concierge_only`-mode offer verified and priced for a different customer's specific sourcing
   request, purely by POSTing it to `/checkout/orders`.
2. The same public detail route disclosed a concierge-only offer's title, price, and supplier
   country to anyone with the id, with no authentication or ownership check possible on that
   route by design.
3. A `reserve`- or `concierge_only`-mode offer could theoretically surface in the customer-facing
   reorder-assessment list or be auto-selected by the replenishment scheduler, in both cases
   feeding back into the same checkout path.

This is exactly the class of defect Workstream 1 describes and required fixing before any
dependent workstream.

## Decision

`Offer.mode` eligibility is enforced at every point an offer is selected for, or converted into,
a customer-facing order or listing:

- `CheckoutService.create_order` gained an `allowed_modes: frozenset[str]` parameter, defaulting
  to `{"full_payment"}`. Every customer-facing checkout call site uses that default. The one
  legitimate internal caller that must pass a non-default value —
  `app.modules.concierge.service.accept_offer`, converting the `concierge_only` offer it just
  created for that exact accepted request — passes `allowed_modes={"concierge_only"}` explicitly,
  matching Workstream 1's "explicit internal application command carrying the trusted workflow
  identifier" requirement rather than a blanket bypass flag. `reserve`-mode conversion
  (`app.modules.reservations.service.approve_and_convert_reservation`) builds its own `Order` row
  directly and was never routed through `CheckoutService`, so it required no change here.
- `_find_available_offer` (replenishment) and `_reorder_options` (customer reorder-assessment)
  both now filter on `Offer.mode == "full_payment"`, keeping their shared "reorderable" definition
  (already called out in both functions' docstrings as deliberately identical) consistent.
- The public `GET /catalog/offers/{offer_id}` route now excludes `mode == "concierge_only"`,
  matching the exclusion `list_offers`/`search_offers`/`list_product_alternatives` already applied
  via `_offer_availability_filters`. A request for a concierge-only offer's id now returns the
  same 404 as an unknown id — non-enumerating, matching this codebase's established convention
  everywhere else. The owning customer retains full access to their own concierge offer via the
  already ownership-checked `GET /concierge-offers/{offer_id}` route and via their order detail's
  own price/title snapshot, neither of which depends on the public catalog route.
- `list_offers`/`search_offers`/`list_product_alternatives` additionally exclude `mode="reserve"`
  offers unless `settings.reserve_now_enabled` is true. There is currently no dedicated
  reserve-discovery UI on the frontend (confirmed by inspection — only `checkout-review.tsx`
  references reserve policy, and only to check the flag before showing a reserve-checkout
  affordance already in a cart/order context); showing a reserve offer in ordinary browse today
  would let a customer add it to cart and then have checkout reject it with no explanation. This
  gate should be revisited once a real reserve-discovery surface exists (Workstream 3).
- `Offer.mode`'s `CheckConstraint` in `app/modules/catalog/models.py` was also found out of sync
  with the database: migration `20260720_0035` (concierge offers) had already widened the actual
  PostgreSQL constraint to include `concierge_only`, but the SQLAlchemy model declaration was
  never updated to match. Fixed to keep the model an accurate reflection of the live schema.

## Compatibility impact

One existing test (`test_accepted_concierge_offer_is_hidden_from_browse_and_search_but_reachable_by_id`,
renamed to `..._but_reachable_by_id` → `..._and_direct_id`) encoded the old, now-superseded
behavior (concierge offer detail reachable by direct id) as its explicit assertion. Updated to
assert the new, correct non-enumerating-404 behavior, with a comment explaining why. No frontend
code was found to depend on the old behavior (verified by grep: nothing under
`src/features/support/` — the concierge feature area — ever navigates to `/shop/offer/[offerId]`).
No other behavior change; no data migration needed (this is an authorization-logic-only change,
no schema change beyond the model/DB drift fix above, which itself changes nothing at runtime
since PostgreSQL was already enforcing the wider constraint).

## Rollback

Revert the commit. No data was written differently by this change (it only narrows which requests
are *accepted*, never changes what gets persisted for an accepted request), so rollback carries no
data-loss risk. Reverting would restore the checkout-bypass exposure described above, so should
only be done alongside an equivalent fix landing another way, not as a bare revert.
