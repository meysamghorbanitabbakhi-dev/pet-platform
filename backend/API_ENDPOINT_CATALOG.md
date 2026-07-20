# API endpoint catalog

The checked OpenAPI contract's path and operation counts are governed by `release-contract.json` (`path_count`, `operation_count`) — do not hardcode them here, and do not conflate the two: one path can expose more than one HTTP operation. Routes use the `/api/v1` prefix except health/docs/internal metrics. Schema details in `docs/api/openapi.json` are authoritative.

## K9 customer integration endpoints

| Method | Endpoint | Capability |
|---|---|---|
| GET | `/me/context` | New-device identity, household, pet, onboarding and capability reconstruction |
| GET | `/pet-life/households/{household_id}/pets` | Deterministic active household pet switcher |
| GET | `/catalog/offers/{offer_id}` | Typed offer detail with Persian content, IRR price, trust and availability |
| GET | `/orders/{order_id}` | Reload-safe typed order detail |
| PUT | `/orders/{order_id}/pet-plan` | Idempotent complete replacement of planned pets for order lines |
| POST | `/orders/{order_id}/delay-acknowledgements` | Idempotently acknowledge visible delivery delay with no compensation implication |
| GET | `/pet-life/inventory/{unit_id}` | Rich household inventory detail with assignments and active estimate |
| POST | `/pet-life/inventory/{unit_id}/reorder-assessment` | Authoritative reorder recommendation from server facts and 3-day safety buffer |
| PUT | `/pet-life/inventory/{unit_id}/reorder-snooze` | Durable 72-hour maximum reorder snooze with approved early-break rule |
| GET | `/pet-life/pets/{pet_id}/today` | Typed Today projection with discriminated food state |
| POST | `/catalog/offers/{offer_id}/availability-subscriptions` | Idempotent availability subscription; never creates commercial records |
| DELETE | `/catalog/offers/{offer_id}/availability-subscriptions` | Idempotent availability cancellation |
| GET | `/me/availability-subscriptions` | Customer availability subscription list |
| POST | `/customer-requests` | Idempotent support/concierge request with no promises |
| GET | `/customer-requests` | Customer request list |
| GET | `/customer-requests/{request_id}` | Customer request detail |
| GET | `/pet-life/pets/{pet_id}/journey-offers` | Approved journey offers; policy-gated |
| GET | `/pet-life/journey-definitions/{definition_id}` | Approved versioned journey detail; policy-gated |
| GET | `/pet-life/journeys/{journey_id}` | Journey detail with ordered check-ins; policy-gated |
| POST | `/pet-life/journeys/{journey_id}/check-ins` | Durable validated journey check-in; policy-gated |
| GET | `/pet-life/pets/{pet_id}/diary/{entry_id}` | Typed diary entry detail |
| GET | `/pet-life/pets/{pet_id}/garden` | Server-derived Garden state |
| PUT | `/pet-life/garden/{reward_id}/placement` | Place/move Garden reward |
| DELETE | `/pet-life/garden/{reward_id}/placement` | Store Garden reward while preserving linked memory |

## Existing customer foundations

| Area | Key endpoints |
|---|---|
| Auth | `POST /auth/otp/request`, `POST /auth/otp/verify`, `POST /auth/session/refresh`, `POST /auth/session/logout` |
| Commerce | `GET /catalog/offers`, `POST /checkout/orders`, `POST /orders/{order_id}/payments/zarinpal`, `GET /payments/zarinpal/callback`, `GET /orders`, `GET /orders/feed`, `GET /orders/{order_id}/journey` |
| Household/Pet Life | Household/address/pet creation, external inventory, assignments, opening/correction/exhaust, wallet, notifications, journeys, diary and Garden |
| Pet profile/health/assets | Profile, breed selection, measurements, reminders, consents, private assets, body assessments and approved care guidance |
| Knowledge/privacy/system | Breed knowledge, pet knowledge, privacy export/request, policy read, health and metrics |
| Operator price intelligence | Internal sources, robots checks, collection runs, observations, pending matches and match decisions; disabled-by-default collection |

## K9 operator endpoints

| Method | Endpoint | Capability |
|---|---|---|
| PUT | `/operator/offers/{offer_id}/capacity` | Updates capacity and emits replay-safe availability notifications when genuinely available |
| GET | `/operator/customer-requests` | Operator customer request queue |
| POST | `/operator/customer-requests/{request_id}/status` | Audited request status transition |
| Existing | Catalog, sourcing, fulfillment, trust, journey-definition, notification, knowledge, privacy and telemetry endpoints | K8 behavior preserved |

## Policy-hidden customer capabilities

There are no executable customer endpoints for refund, replacement, substitution or delay compensation. Push notifications are not claimed in K9. Self-service order cancellation exists but only up to the supplier financial-commitment boundary — see Workstream 2B below; there is still no customer-facing cancellation once a supplier has been committed. Reserve-now (Workstream 2C, see below) is now fully built and endpoint-reachable but gated behind `reserve_now_enabled=false` — every reserve-now request 409s until that flag is explicitly turned on.

## Design-contract closure endpoints (2026-07-19)

Added to close the last open rows of the accepted 152-state design contract (G5-AUTH-02, G5-SHOP-13, G5-SHOP-14) — see `frontend/docs/design-state-implementation-matrix.md`.

| Method | Endpoint | Capability |
|---|---|---|
| GET | `/catalog/offers/search` | Backend-owned, Persian-normalized (ی/ي, ک/ك, diacritics, ZWNJ, casefold) substring search over title and SKU; bounded `OffsetPage`, deterministic ordering, same availability filtering as `/catalog/offers` |
| GET | `/catalog/products/{product_id}/alternatives` | Public read of operator-approved product alternatives, revalidated against currently-available offers at read time |
| POST | `/operator/product-alternatives` | Operator proposes a directed product-to-product alternative (self-reference and duplicate pairs rejected) |
| GET | `/operator/product-alternatives` | Operator list/review queue, filterable by status and source product |
| PATCH | `/operator/product-alternatives/{alternative_id}` | Operator edits rationale/compatibility notes/rank; rejected once retired |
| POST | `/operator/product-alternatives/{alternative_id}/approve` | Operator approval; idempotent (replaying an already-approved id is a no-op, not a duplicate audit entry) |
| POST | `/operator/product-alternatives/{alternative_id}/retire` | Operator retirement; idempotent |

No customer-facing operator UI exists for product alternatives, matching every other operator capability in this catalog (price intelligence, supplier management, etc.) — operator routes are API-only by established convention.

## Purchasing batch endpoints (2026-07-19, Workstream 2A)

Aggregated/individual purchasing-cycle management. Every paid order line is allocated to a batch at payment-verification time (not through these endpoints); operators use these to configure sourcing routing and record the durable supplier financial-commitment fact that Workstream 2B's cancellation boundary reads. See `docs/adr/ADR-006-purchasing-batch-architecture.md`.

| Method | Endpoint | Capability |
|---|---|---|
| PATCH | `/operator/offers/{offer_id}/sourcing-config` | Sets an offer's explicit, operator-chosen sourcing route (`aggregated`\|`individual`) and default batch threshold quantity — never inferred |
| GET | `/operator/purchase-batches` | Batch list/queue, filterable by offer and status |
| GET | `/operator/purchase-batches/{batch_id}` | Batch detail with allocations and append-only status-history events |
| PATCH | `/operator/purchase-batches/{batch_id}` | Adjusts threshold/deadline while a batch is still open; a lowered threshold that the batch already meets retroactively records `threshold_reached`, but a later raise never un-sets an already-reached fact |
| POST | `/operator/purchase-batches/{batch_id}/commit` | Records the operator-evidenced supplier financial commitment; idempotent (replaying an already-committed batch is a no-op, not a duplicate audit entry) |

No customer-facing endpoints exist for purchasing batches — customers never see batch/pooling mechanics directly.

## Customer order cancellation (2026-07-19, Workstream 2B)

Cancellation before supplier financial commitment. Eligibility is governed by the durable batch-commitment fact from Workstream 2A (`PurchaseBatch.committed_at`, not bare order status), checked under the same row locks `commit_batch` takes, so the cancel-vs-commit race is linearizable. Refunds are operator-attested (manual), never an automatic payment-gateway reversal — `refund_status` starts `owed`; `POST /operator/order-cancellations/{cancellation_id}/attest-refund` (added with Workstream 2E, see below) transitions it to `operator_attested`.

| Method | Endpoint | Capability |
|---|---|---|
| POST | `/orders/{order_id}/cancel` | Customer cancellation with a required reason; idempotent (replaying an already-cancelled order returns the same record); non-enumerating 404 for a nonexistent or not-owned order; 409 once the order's batch is already committed |

`GET /orders/{order_id}` now also returns `cancellation_eligible` (whether this endpoint would currently succeed) and `cancellation` (the cancellation + refund-owed record, once one exists).

## Shelf-life exceptions (2026-07-19, Workstream 2E)

`POST /operator/order-lines/{line_id}/confirm-sourced`'s existing hard block (rejecting a sourced unit whose exact expiry falls short of the offer's `minimum_shelf_life_months` guarantee) now has an explicit escape hatch: an operator-proposed exception the customer must accept or decline. There is no fulfillment path around this — `SourcedUnitEvidence`, which delivery projection requires for every line, is only created on acceptance. Refunds are operator-attested (manual), the same mechanism and product decision as Workstream 2B's order cancellation.

| Method | Endpoint | Capability |
|---|---|---|
| POST | `/operator/order-lines/{line_id}/shelf-life-exceptions` | Operator proposes an exception (exact expiry, additional discount, reason, evidence) for a line that would otherwise hard-block; rejected if the expiry actually meets the guarantee, the line is already sourced, or an exception already exists for it |
| GET | `/operator/shelf-life-exceptions` | Operator list/queue, filterable by status |
| GET | `/operator/shelf-life-exceptions/{exception_id}` | Operator detail |
| POST | `/operator/shelf-life-exceptions/{exception_id}/attest-refund` | Operator-attested manual refund once `refund_status` is `owed`; idempotent |
| POST | `/operator/order-cancellations/{cancellation_id}/attest-refund` | Same mechanism, for Workstream 2B order cancellations |
| GET | `/orders/{order_id}/shelf-life-exceptions` | Customer list for their own order |
| POST | `/orders/{order_id}/shelf-life-exceptions/{exception_id}/accept` | Customer accepts the shorter expiry (and any discount); creates the sourced-unit evidence that unblocks delivery for that line; idempotent |
| POST | `/orders/{order_id}/shelf-life-exceptions/{exception_id}/decline` | Customer declines; the full line total becomes refund-owed and the line is excluded from delivery projection (the order's *other* lines are unaffected); idempotent |

An unanswered exception automatically becomes `expired` (same refund outcome as a decline) via a scheduler sweep once its response deadline passes; both accept and decline also self-expire on a late response, so a race between a customer's click and the sweep can never produce an inconsistent state. Concurrent accept-vs-decline on the same exception is resolved by row lock — proven under real concurrency, not just reasoned about.

## Reserve-now (2026-07-19, Workstream 2C — gated off, `reserve_now_enabled=false`)

Zero-charge reservation → operator source/price reconfirmation and proposal → customer approval → full-payment order, with no deposit concept anywhere in the schema. Fully built and tested but every endpoint below returns `409 reserve_now_disabled` while the flag is off — see `docs/runbooks/reserve-now-rollout.md` and ADR-008 before ever turning it on.

| Method | Endpoint | Capability |
|---|---|---|
| POST | `/reservations` | Customer zero-charge reservation request for a `mode='reserve'` offer; idempotent |
| GET | `/reservations` | Customer list of their own reservations |
| GET | `/reservations/{reservation_id}` | Customer detail; non-enumerating 404 for a missing or foreign reservation |
| POST | `/reservations/{reservation_id}/approve` | Customer approves the operator-reconfirmed terms; creates a real, full-payment `Order` at the *reconfirmed* price (never whatever the live offer price happens to be at that instant) and returns it for the existing payment flow; idempotent, returns the same order on replay |
| POST | `/reservations/{reservation_id}/decline` | Customer declines the proposed terms; idempotent |
| POST | `/operator/reservations/{reservation_id}/reconfirm-and-propose` | Operator reconfirms current price/availability and proposes it to the customer for approval; idempotent |
| POST | `/operator/reservations/{reservation_id}/decline` | Operator determines the offer cannot be sourced at all, skipping the customer entirely; idempotent |
| GET | `/operator/reservations` | Operator list/queue, filterable by status |
| GET | `/operator/reservations/{reservation_id}` | Operator detail |

No frontend UI exists for reserve-now yet (unlike Workstreams 2A/2B/2E's live customer endpoints) — building it against endpoints that always 409 would be unverifiable, so it is deferred to whichever future pass enables the flag.

## Replenishment reservations (2026-07-19, Workstream 3 — gated off, `replenishment_reservation_enabled=false`)

System-proposed reorder per inventory unit → customer explicit approval (real full-payment order
at the live offer price) or decline, with no deposit or auto-charge concept anywhere in the
schema. Fully built, tested, and has frontend UI (inventory-unit panel + Today summary banner),
but every endpoint below returns `409 replenishment_reservation_disabled` while the flag is off —
see `docs/runbooks/replenishment-reservation-rollout.md` and ADR-009 before ever turning it on.

| Method | Endpoint | Capability |
|---|---|---|
| GET | `/pet-life/households/{household_id}/replenishment-reservations` | Customer list of a household's replenishment reservations |
| GET | `/pet-life/replenishment-reservations/{reservation_id}` | Customer detail; non-enumerating 404 for a missing or foreign-household reservation |
| POST | `/pet-life/replenishment-reservations/{reservation_id}/approve` | Customer approves; creates a real, full-payment `Order` at the *live* offer price (no reconfirmed-price step, unlike reserve-now) for the existing payment flow; idempotent, returns the same order on replay |
| POST | `/pet-life/replenishment-reservations/{reservation_id}/decline` | Customer declines the proposed reservation; idempotent |

Reservations themselves are created and refreshed by a scheduler job (not a customer-initiated
endpoint), and refreshed or invalidated in place by the pre-existing
`POST /pet-life/inventory/{unit_id}/estimate/correct` and
`POST /pet-life/inventory/{unit_id}/exhaust` endpoints — see ADR-009.

## Verified concierge offers (2026-07-20, Workstream 4 — gated off, `concierge_offers_enabled=false`)

Extends the existing `support_customer_requests` (`request_type='concierge_sourcing'`) queue with
an auditable, verified-offer lifecycle: operator review → evidence-backed presentation (hybrid
reference-price-savings or landed-cost-plus-margin pricing, Decision 0.34) → customer explicit
accept (real full-payment order via a one-off catalog offer, hidden until a deliberate operator
promotion) or decline, with no deposit or auto-charge concept anywhere in the schema. Fully built,
tested, and has customer-facing frontend UI on the existing request-detail page, but every
endpoint below returns `409 concierge_offers_disabled` while the flag is off — see
`docs/runbooks/concierge-offer-rollout.md` and ADR-010 before ever turning it on. Note
`concierge_requests_enabled` (already live) is a separate, pre-existing flag gating request
*submission*, unaffected by this one.

| Method | Endpoint | Capability |
|---|---|---|
| GET | `/customer-requests/{request_id}/concierge-offers` | Customer list of a request's offer cycles (most recent first); customer-safe fields only |
| GET | `/concierge-offers/{offer_id}` | Customer detail; non-enumerating 404 for a missing or foreign offer |
| POST | `/concierge-offers/{offer_id}/accept` | Customer accepts; lazily creates a one-off `Offer(mode='concierge_only')` and a real, full-payment `Order` at the presented (locked) price; idempotent, returns the same offer/order on replay |
| POST | `/concierge-offers/{offer_id}/decline` | Customer declines the presented offer; idempotent |
| POST | `/concierge-offers/{offer_id}/refresh` | Customer requests a fresh look at an *expired* offer; creates a new cycle, never reactivates the old row; idempotent while a cycle is already active |
| POST | `/operator/customer-requests/{request_id}/concierge-offers/start-review` | Operator begins (or resumes, for a refresh cycle) verification; idempotent |
| POST | `/operator/concierge-offers/{offer_id}/present` | Operator presents a verified, evidence-backed, priced offer with a 12-48h validity window; idempotent and immutable once presented |
| POST | `/operator/concierge-offers/{offer_id}/unavailable` | Operator determines the request cannot be sourced at all, skipping the customer entirely; idempotent |
| POST | `/operator/concierge-offers/{offer_id}/promote` | Operator-discretion catalog promotion of an already-accepted offer's one-off `Offer` (Decision 0.37); idempotent |
| GET | `/operator/concierge-offers` | Operator queue, filterable by `status` |
| GET | `/operator/concierge-offers/{offer_id}` | Operator detail, including internal landed-cost components and supplier identity — never returned from a customer-facing route |
