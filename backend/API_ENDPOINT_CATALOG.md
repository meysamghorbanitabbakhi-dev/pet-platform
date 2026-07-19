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

There are no executable customer endpoints for reserve-now, self-service cancellation after sourcing, refund, replacement, substitution or delay compensation. Push notifications are not claimed in K9.

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
