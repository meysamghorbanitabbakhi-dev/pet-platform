# Frontend integration contract

Generate the authoritative schema with:

```bash
python -m app.cli.export_openapi --output docs/api/openapi.json
```

Generate typed frontend clients from that checked artifact, not from handwritten endpoint types. CI verifies that `docs/api/openapi.json` exactly matches the application OpenAPI document.

## Core conventions

All money is integer IRR. Canonical monetary values use explicit `*_irr` fields; do not convert them to floating-point numbers. `GET /api/v1/system/policies` provides the canonical currency and customer display-unit metadata. All timestamps are timezone-aware ISO 8601.

Mutating commerce endpoints requiring `Idempotency-Key` must reuse the same key only for an identical request. Payment verification still precedes sourcing. Supplier identity is private and must not be inferred from customer contracts.

Errors use `error.code`, `error.message`, optional `error.details`, and `error.request_id`. Display localized UX copy by stable code; retain the request ID for support. Never expose raw provider errors.

## Typed pages and cursors

Collection endpoints expose bounded offset paging with this K8-compatible shape:

```json
{
  "items": [],
  "page": {"limit": 25, "offset": 0, "total": 0, "has_more": false}
}
```

For continuously growing orders and inbox data, prefer `/api/v1/orders/feed` and `/api/v1/pet-life/notifications/feed`. They return:

```json
{
  "items": [],
  "page": {"next_cursor": null, "has_more": false}
}
```

The opaque cursor is signed, must never be edited by clients, and is passed back exactly as `cursor`. A missing `next_cursor` means the current traversal is complete.

## Today state unions

`GET /api/v1/pet-life/pets/{pet_id}/today` has discriminated `food` and `primary_attention` contracts. Switch on `food.state` (`none`, `incoming`, `unopened`, `unknown_estimate`, `estimated`, or `unavailable`) and on `primary_attention.type` when attention is present. Incoming food appears only for pets named in an order-line plan. Incoming and unopened states intentionally have no remaining-days field. Unknown shares produce no pet-level remaining-days value. Active reorder snoozes suppress reorder attention until their server-owned expiry.

## K9.1 bootstrap and commerce

`GET /api/v1/me/context` reconstructs the authenticated customer, accessible households, active pets, deterministic single-household default, onboarding requirements, and routing flags without side effects. `GET /api/v1/pet-life/households/{household_id}/pets` is household-authorized and deterministically ordered.

`GET /api/v1/catalog/offers/{offer_id}` returns only active or temporarily unavailable curated offers. Its media entries are ordered public references; supplier identity and storage paths are never included. Savings use integer floor percentage: `(reference_price_irr - price_irr) * 100 // reference_price_irr`.

`GET /api/v1/orders/{order_id}` is the reload-safe order projection. `PUT /api/v1/orders/{order_id}/pet-plan` replaces line-to-pet assignments while the order is paid, sourcing, or in transit. It is idempotent, has no inventory-opening or estimation effect, and delivery projects planned pets as unknown-share unopened assignments.

## K9.2 inventory, estimates, and reorder

`GET /api/v1/pet-life/inventory/{unit_id}` is the typed inventory detail. It returns the unit, product/source/state facts, known quantities, timestamps, expiry/assurance snapshot, assignments, `shares_known`, and the active household estimate when one exists.

Opening or correcting inventory accepts either the legacy `remaining_grams` field or the versioned `remaining` union. Exact grams (`{"mode":"grams","grams":2100}`) preserves the input, stores grams bounds with identical low/high values, and records provenance. Level input (`{"mode":"level","level":"more_than_half"}`) is schema-valid but currently fails closed with `semantic_level_policy_disabled`; clients must not convert levels to guessed grams.

`POST /api/v1/pet-life/inventory/{unit_id}/reorder-assessment` is authoritative for reorder UX. It uses server-owned estimate, delivery policy, configured safety buffer, offer availability/capacity, and active snooze. When the safety buffer is not configured, it returns `outcome=policy_blocked`; when facts are insufficient, it returns `outcome=insufficient_facts`. `PUT /api/v1/pet-life/inventory/{unit_id}/reorder-snooze` is durable and idempotent for an active snooze with a maximum of 72 hours.

## K9.3 customer experience

Availability subscriptions are managed with `POST/DELETE /api/v1/catalog/offers/{offer_id}/availability-subscriptions` and listed at `GET /api/v1/me/availability-subscriptions`. Responses always include `order_created=false`; subscribing or cancelling never creates orders, payments, sourcing, or inventory. Availability notifications are in-app/SMS only and replay-safe once per activation cycle; there is no push-channel claim.

`POST /api/v1/customer-requests` requires `Idempotency-Key` and creates either `support` or `concierge_sourcing` requests. It validates household and referenced order/offer ownership, returns explicit false promises for availability, response time, refund, replacement, and sourcing success, and never auto-creates catalog products. Operators can list requests and audit status changes through `/api/v1/operator/customer-requests`.

`POST /api/v1/orders/{order_id}/delay-acknowledgements` requires a visible delay and `Idempotency-Key`. The response records the delay event version and explicitly states no compensation, cancellation, waiver, or resolution implication.

Journey discovery/detail/check-ins are available under `/api/v1/pet-life/*` only when care journey delivery is enabled. Definitions must be approved, active, eligible, and professionally referenced. Check-ins validate server-side allowed answers and completion requirements; completion creates at most one diary memory and one Garden reward. Diary detail is typed at `/api/v1/pet-life/pets/{pet_id}/diary/{entry_id}`. Garden state is server-derived, has no XP/decay/purchase rewards, and `DELETE /api/v1/pet-life/garden/{reward_id}/placement` stores an object while preserving its memory link.

## Policy posture

`GET /api/v1/system/policies` is the frontend feature boundary. K9.0 exposes `currency_code=IRR`, `customer_display_unit=TOMAN`, and `irr_per_customer_display_unit=10`; all API money remains integer `*_irr` and must not be silently rounded into toman. Late-credit execution/customer visibility, reserve-now, cancellation after sourcing, self-service refund/replacement/substitution, and customer-visible delay compensation are off. Availability-subscription and concierge-request metadata is on, but K9.0 supplies no customer workflow for either; a flag never authorizes a new endpoint. See `docs/adr/ADR-004-k9-policy-boundaries.md` for decisions marked **POLICY BLOCKED**.

The deterministic demo scenario is `fixtures/demo/v1.json`. It is sample data, not a claim that its product, price, nutritional content, or operational state exists in production.
