# ADR-009 — Replenishment reservation architecture and why it reuses checkout instead of forking it

**Status:** Approved
**Date:** 2026-07-19

## Context

Workstream 3 asks for a *system-proposed* reorder: when an inventory unit's pessimistic depletion
estimate crosses a lead time, the platform should reserve the likely replenishment for the
customer to review and approve, never auto-charging. This is already a locked product decision
(`pet_platform_product_decision_record.md`, Part XI, Decisions 0.29-0.31): reservation is not a
paid order, no payment or sourcing happens automatically, the reservation is created 14 days
before predicted depletion, and the customer has 48 hours to approve before it expires with no
sourcing slot held. This ADR is about how that decision is implemented on top of the pre-existing
food-estimate/inventory/reorder-assessment domain (`app/modules/food_estimation`,
`app/modules/inventory`, `app/modules/replenishment/service.py`'s `assess_reorder`), and why it
deliberately does *not* fork reserve-now's (ADR-008) reconfirmed-price pattern.

## Decision

1. **One reservation per inventory unit, ever.** `ReplenishmentReservation.inventory_unit_id` is a
   full (non-partial) `UniqueConstraint`, not the "multiple attempts allowed" model ADR-008 uses
   for reserve-now. A unit has exactly one consumption cycle from opened to exhausted — one "need
   window" — so a resolved reservation (`approved`/`declined`/`expired`/`invalidated`) is never
   superseded by a second row for the same unit. This is a materially different shape from
   reserve-now's repeatable customer-initiated request.
2. **Created only from sufficient facts, never fabricated.** The scheduler
   (`scan_and_create_due_reservations`) creates a reservation only when
   `FoodEstimate.low_days` is known and at or below `replenishment_reservation_lead_days` (default
   14) *and* a reorderable offer exists for the unit's product (the same "available" definition
   `_reorder_options`/`inventory_reorder_assessment` already use: `status=active`,
   `stock_posture=sourced_after_payment`, `sourcing_capacity_status=open`). No estimate, an
   unknown-share estimate, or no offer means no reservation — silently, not as an error state.
3. **Refresh in place, never a second row.** If a reservation is still `pending_approval` and a
   newer active `FoodEstimate` exists with a different low/high range, `predicted_depletion_*` and
   `source_food_estimate_id` are updated on the same row (plus a `refreshed` event); the unique
   constraint in point 1 makes a duplicate structurally impossible even under concurrent scheduler
   ticks and customer-triggered corrections (both paths row-lock the `InventoryUnit` first). The
   approval deadline is *not* extended by a refresh — the customer's response window is bounded and
   predictable, not push-able indefinitely by the estimate simply changing.
4. **Approval reuses `CheckoutService.create_order` directly, unlike ADR-008's reserve-now.**
   Reserve-now bypasses `CheckoutService` because it must charge the price reconfirmed by an
   operator, not the live offer price. Replenishment reservations have no reconfirmation step at
   all — the product decision record's "reviews product, quantity, price" language describes a
   preview, not a locked quote — so approving is architecturally identical to a manual reorder:
   the customer approves, and `CheckoutService.create_order` prices the resulting Order at
   whatever `offer.price_irr` is at that moment, exactly as if they had reordered by hand. Reusing
   the existing path avoids duplicating order-creation logic for no behavioral reason.
5. **The customer-visible price is explicitly informational.** The frontend shows the current
   `offer.price_irr` (fetched live via the existing `GET /catalog/offers/{offer_id}`, not a
   snapshot column) next to "(تقریبی)" ("approximate") wording, and the approval confirmation
   restates that the order is created at the live price. This satisfies Decision 0.29's "reviews
   ... price" rule without inventing a second, competing notion of a locked price alongside
   point 4's live-price approval.
6. **Lazy self-expiry plus a sweep, one final reminder.** `approve_reservation`/
   `decline_reservation` self-check `approval_expires_at` before acting (a response arriving after
   the deadline resolves to `expired`, never a late approval), and
   `expire_stale_reservations` is the scheduler sweep for reservations nobody answered. Both set
   `reminder_sent_at` exactly once — the "final reminder then stop" rule from the brief — never a
   second notification. This is the same lazy-expiry shape as ADR-008's two independent deadlines
   and Workstream 2E's shelf-life exceptions, applied to replenishment's single deadline.
7. **`correct_estimate`/`exhaust_inventory` are hook points, not new endpoints.** A correction is
   new facts about the *same* still-open unit, not a new need window: it calls
   `create_or_refresh_reservation_for_unit` (refresh-or-create, point 3), never invalidates.
   Exhaustion closes the need window out entirely: it calls `invalidate_reservation_for_unit`,
   which only touches a still-`pending_approval` row — an already-`approved` reservation (a real
   Order exists) is never retroactively invalidated by a later exhaustion.
8. **Ships live at the code level, reachable only behind `replenishment_reservation_enabled`.**
   Every customer endpoint checks the flag first (`409 replenishment_reservation_disabled`), the
   scheduler jobs are only registered when the flag is on, and the frontend gates both the
   inventory-detail panel and the Today summary banner on the same flag — the same convention
   `reserve_now_enabled`/`care_journey_delivery_enabled` already use. Unlike ADR-008's reserve-now,
   this workstream *does* ship frontend UI behind the flag (the brief explicitly requires
   Today/inventory UI), verified end-to-end with the flag forced on in both backend and component
   tests.

## Consequences

- Detail/approve/decline endpoints resolve access via household membership
  (`_household_access_for_replenishment_reservation`), not a direct `customer_identity_id` column
  comparison the way reserve-now's `Reservation` does — `ReplenishmentReservation` is a
  household-level resource (like `InventoryUnit`/`FoodEstimate` themselves), not an
  identity-owned one. A dedicated helper (distinct from the generic `_household_access`) always
  raises the *reservation's* 404 code even when the underlying cause is "wrong household," so the
  error response never distinguishes "doesn't exist" from "exists in a household you can't
  access" — the non-enumeration property Workstream 5E asks for generally, applied here from the
  start rather than retrofitted.
- No deposit column exists anywhere in this schema, the same structural argument ADR-008 makes:
  there is nothing to charge until `approve_reservation` creates a normal `Order` in
  `awaiting_payment`, which then goes through the unmodified `PaymentService`/Zarinpal flow.
  `ReplenishmentReservationResponse.auto_charged` is a typed `Literal[False]`, matching the
  `deposit_charged_irr`/`refund_auto_processed` idiom already used elsewhere.
- The scheduler's per-unit scan does one query per candidate unit for its active estimate and one
  for its offer (an N+1 shape), matching the existing style of `_reorder_options`/
  `inventory_reorder_assessment` rather than a hand-optimized batch join — accepted for the same
  reason those endpoints accept it: the expected data volume for a niche commerce platform does
  not justify the added complexity.
