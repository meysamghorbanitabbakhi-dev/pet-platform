# Backend Gate K9 — Frontend Integration Completion

**Implementation brief for the backend developer**  
**Baseline:** complete Gate K8 backend snapshot and PET-FE-DESIGN-v1  
**Objective:** add the backend contracts required by the approved customer frontend without weakening the household, trust, financial, privacy or veterinary-governance boundaries.

## 1. Required outcome

Extend K8 into an integration-ready customer API supporting:

- deterministic post-login household and pet bootstrap;
- strongly typed customer responses;
- complete offer, order, inventory and Today projections;
- optional order-line-to-pet planning without starting consumption;
- semantic food-quantity inputs without client-side guesses;
- availability subscriptions and persisted reorder snoozing;
- factual delay acknowledgements;
- customer support and concierge requests;
- approved journey discovery, detail and check-ins;
- rich diary and Persian Garden state;
- reliable generated OpenAPI clients.

This gate extends K8. It is not a rewrite.

## 2. Non-negotiable rules

1. Household remains the ownership, payment, address, order, wallet and inventory boundary.
2. Pet remains the experience, assignment, measurement, journey, diary and Garden boundary.
3. The platform remains the merchant/operator; do not add marketplace or seller capabilities.
4. Full verified payment must precede sourcing.
5. Delivery creates unopened household inventory only and never starts an estimate.
6. Estimates begin only after explicit confirmed opening.
7. Unknown shares must never produce fake per-pet precision.
8. Availability subscription must never create an order.
9. Order planning is not consumption and must not create an estimate.
10. Supplier identity remains private; customer responses may expose country and supplier-verified assurance only.
11. Before payment expose minimum shelf-life; after sourcing expose exact expiry.
12. Never expose “100% authentic” or equivalent wording.
13. Dates, prices, order states and delivery facts remain literal.
14. Garden rewards never come from purchases, spending, app opens, taps, streaks or XP.
15. Journey/care content fails closed unless professionally approved and currently eligible.
16. Do not activate reserve-now, customer cancellation, refund, replacement, substitution or compensation promises in this gate.
17. Customer resources require household authorization and non-enumerating 404 behavior.
18. Persist UTC and return timezone-aware ISO 8601 timestamps.
19. Monetary values remain canonical integer IRR in storage and transport.
20. Redis remains non-authoritative; durable decisions belong in PostgreSQL.

## 3. Policy reconciliation before release

The developer must not silently choose product policy. Implement configurable fields and block release until founder decisions are recorded.

### 3.1 Delivery commitment

Current conflict: frontend research/design says 14 days; K8 uses exactly 366 hours.

Required:

- keep commitment server-side;
- expose delivery_commitment_hours from /system/policies;
- issue and persist exact delivery_commitment_at after verified payment;
- never ask frontend to calculate the promised timestamp;
- do not hard-code either promise into customer copy;
- record the final decision in an ADR and automated policy test.

Until confirmed, retain K8 runtime behavior to avoid an unreviewed operational change, but report the release as POLICY BLOCKED.

### 3.2 IRR and toman

Backend values remain integer IRR. Add these policy fields:

    currency_code: IRR
    customer_display_unit: TOMAN
    irr_per_customer_display_unit: 10

Never return an ambiguous bare price; use _irr suffixes. Do not perform hidden backend rounding into toman.

### 3.3 Late credit

K8 contains 5% late-credit logic while the frontend and final handoff treat customer-facing compensation as gated.

Add and enforce:

    late_credit_enabled
    late_credit_basis_points
    late_credit_expiry_months
    late_credit_customer_visible

The scheduler grants credit only when enabled. Customer DTOs reveal reason/amount only when customer-visible. Default both booleans to false pending the recorded decision; preserve existing logic behind flags.

### 3.4 Feature flags

Extend /system/policies:

    reserve_now_enabled=false
    cancel_after_sourcing_enabled=false
    refund_self_service_enabled=false
    replacement_self_service_enabled=false
    substitution_self_service_enabled=false
    delay_compensation_customer_visible=false
    availability_subscriptions_enabled=true
    concierge_requests_enabled=true
    care_journey_customer_delivery_enabled=<runtime>

Disabled features must not leak placeholders or promises through customer APIs.

## 4. K9.0 — Strongly typed API contract

Replace generic customer dict/list responses with named Pydantic schemas.

At minimum create:

- MeContextResponse, HouseholdSummary, PetSummary, AddressResponse;
- OfferListItem and OfferDetailResponse;
- OrderListItem, OrderDetailResponse, OrderJourneyResponse and SourcedUnitResponse;
- InventoryListItem, InventoryDetailResponse and ConsumptionAssignmentResponse;
- FoodEstimateResponse and FoodEstimateProvenanceRow;
- discriminated TodayResponse module states;
- ReorderAssessmentResponse;
- JourneyOfferResponse, JourneyDefinitionResponse, PetJourneyResponse and JourneyCheckInResponse;
- DiaryListItem and DiaryDetailResponse;
- GardenStateResponse, GardenObjectResponse and GardenEligibilityResponse;
- typed notification inbox/feed and WalletSummaryResponse;
- named responses for existing profile, health, asset, knowledge and privacy endpoints.

Create reusable contracts:

    OffsetPage[T] = items, total, limit, offset
    CursorPage[T] = items, next_cursor
    MoneyIRR = amount_irr, currency=IRR

Requirements:

- OpenAPI describes every response field and enum.
- Machine state keys remain stable English identifiers; localization stays in frontend.
- Use discriminated unions for Today food and attention states.
- Preserve compatibility or version breaking changes explicitly.
- Update checked OpenAPI and fail CI when it differs from the app.

## 5. K9.1 — Identity bootstrap

Add:

    GET /api/v1/me/context

Return:

    identity: id, mobile_e164, identity_type
    households[]: id, name, role, pet_count, active_address_count
    default_household_id: UUID or null
    pets[]: id, household_id, name, species, optional avatar reference
    onboarding: needs_household, needs_pet, needs_address
    customer capability flags needed for routing

Rules:

- GET has no side effects.
- In the single-household launch model, that household is default.
- With multiple households, use a persisted preference or null; never choose nondeterministically.
- Returning users reconstruct context without locally remembered UUIDs.

Add:

    GET /api/v1/pet-life/households/{household_id}/pets

Return deterministically ordered active PetSummary items and enforce membership.

Keep and type household, address, pet creation and profile endpoints. Address edit/delete is excluded unless separately approved.

## 6. K9.1 — Catalog and offer detail

Add migrations for:

- nullable positive catalog_products.nominal_quantity_grams;
- catalog_product_media with product ID, media type, safe storage/public reference, Persian alt text, sort order and active state.

Never expose filesystem paths.

Keep and type:

    GET /api/v1/catalog/offers

Add:

    GET /api/v1/catalog/offers/{offer_id}

Offer detail remains available for active and temporarily unavailable offers so subscriptions target a real offer. Retired/internal records stay hidden.

Return:

- offer/product IDs and SKU;
- Persian title/description;
- unit label and nominal quantity grams;
- ordered media;
- availability/status and factual reason key;
- price_irr and optional reference_price_irr;
- server-calculated saving_percent with documented rounding;
- reference_price_reviewed_at;
- supplier_country_code;
- authenticity=supplier_verified;
- minimum_shelf_life_months_at_delivery;
- customer-relevant availability dates.

Never expose supplier ID/name. Curated alternatives may be deferred; never auto-substitute.

## 7. K9.1 — Complete order contract

Add:

    GET /api/v1/orders/{order_id}

Return a reload-safe order:

- ID, status, currency and merchandise_total_irr;
- created_at and paid_at;
- delivery_commitment_at and original_delivery_commitment_at;
- revised_delivery_at when confirmed;
- delivered_at;
- safe payment summary;
- immutable address snapshot;
- lines with title, SKU, unit, quantity, unit price and line total;
- line-level planned pet IDs;
- sourced-unit customer evidence;
- customer-visible policy fields only.

Type and preserve /orders, /orders/feed and /orders/{id}/journey. Journey returns original/current commitment timestamps, delivery timestamp, ordered confirmed events and sourced-unit expiry/country evidence. Exclude internal notes and provider payloads.

### 7.1 Order-line pet plan

Add orders_order_line_pet_plans with a unique order-line/pet pair.

Add:

    PUT /api/v1/orders/{order_id}/pet-plan

Body:

    {
      "lines": [
        {"order_line_id": "uuid", "pet_ids": ["uuid"]}
      ]
    }

Rules:

- validate lines and pets belong to the order household;
- PUT replaces the complete plan and is idempotent;
- allow during paid, sourcing and in-transit;
- create no estimate and never open inventory;
- on delivery copy the plan into inventory assignments with unknown shares and no portions;
- without a plan, inventory remains unassigned;
- after delivery use the existing inventory assignment endpoint.

### 7.2 Delay acknowledgement

Add a durable idempotent record and:

    POST /api/v1/orders/{order_id}/delay-acknowledgements
    Idempotency-Key: <key>

Store identity, order, acknowledged delay event/version and timestamp. Reject when no visible delay exists. This never implies compensation, cancellation, resolution or waiver of rights.

## 8. K9.2 — Rich inventory and estimates

Type household inventory and add:

    GET /api/v1/pet-life/inventory/{unit_id}

Return:

- unit and household IDs;
- product summary and label;
- source and state;
- known quantities;
- delivery/open timestamps;
- exact expiry and assurance snapshot;
- assignments with pet summaries, shares and portions;
- shares_known;
- active estimate.

### 8.1 Semantic remaining quantity

The frontend must not map semantic choices into guessed grams. Introduce a versioned input union.

Level input:

    {
      "remaining": {
        "mode": "level",
        "level": "full | more_than_half | less_than_half | near_empty"
      },
      "daily_portion_grams": 85,
      "feeding_context": "exclusive | mixed | unknown"
    }

Exact input:

    {
      "remaining": {"mode": "grams", "grams": 2100},
      "daily_portion_grams": 85,
      "feeding_context": "exclusive"
    }

Server requirements:

- preserve exact-grams input;
- store input mode and provenance;
- use nominal product quantity for level-based bounds;
- store low/high remaining bounds instead of fake exact values;
- version and test the level-to-range mapping;
- return honest unknown when facts are insufficient;
- do not infer mixed-feeding share;
- never return per-pet estimates when shares are unknown.

The product owner must approve percentage bounds. Ship the schema but keep level-based calculation disabled until approved if necessary. Preserve the existing grams body temporarily and mark it deprecated only after the new contract passes.

### 8.2 Food estimate response

Return:

- estimate and inventory IDs;
- scope: household or pet;
- optional pet ID;
- min_days and max_days;
- confidence: high, mid or unknown;
- basis key;
- calculated_at and last_confirmed_at;
- provenance rows with field key, source and safe value.

Known shares may yield separate pet projections. Unknown shares yield household scope only.

Keep exhaustion atomic: exhausted inventory exhausts active estimates and appears correctly in Inventory and Today.

## 9. K9.2 — Authoritative replenishment and snoozing

Keep the stateless /pet-life/reorder/assess for compatibility. Add:

    POST /api/v1/pet-life/inventory/{unit_id}/reorder-assessment

Use authoritative:

- active estimate;
- current delivery policy;
- approved safety buffer;
- offer availability/capacity;
- active snooze.

Return recommendation key, risk gap, remaining range, delivery input, safety buffer, calculation provenance, factual options and snoozed_until.

Add:

    PUT /api/v1/pet-life/inventory/{unit_id}/reorder-snooze

Rules:

- server sets a maximum 72-hour snooze;
- persist household/inventory/identity, start/end and baseline pessimistic bound;
- Today suppresses the card during snooze;
- break early only when the server-calculated pessimistic bound materially worsens under a documented rule;
- repeated identical requests are idempotent;
- snoozing changes no inventory or delivery facts.

## 10. K9.2 — Typed Today projection

Replace the generic Today dictionary with a typed response:

- pet summary and household ID;
- generated_at;
- food module union;
- at most one primary attention item;
- optional active journey summary;
- compact Garden preview;
- at most one approved quiet guidance item.

Food states:

    none
    incoming
    unopened
    unknown_estimate
    estimated
    unavailable

Rules:

- incoming appears only when an order-line pet plan includes the pet;
- do not show the latest household order to every pet;
- incoming/unopened never includes remaining-day estimates;
- unknown shares return household scope and no per-pet number;
- one module failure must not invalidate unrelated modules;
- attention priority is deterministic and documented;
- guidance remains quiet and approval-gated.

## 11. K9.3 — Availability subscriptions

Add catalog_availability_subscriptions:

- identity_id;
- household_id if needed;
- offer_id;
- status: active, notified or cancelled;
- created_at, notified_at and cancelled_at;
- unique active identity/offer constraint.

Add:

    POST   /api/v1/catalog/offers/{offer_id}/availability-subscriptions
    DELETE /api/v1/catalog/offers/{offer_id}/availability-subscriptions
    GET    /api/v1/me/availability-subscriptions

Requirements:

- POST is idempotent;
- response explicitly includes order_created=false;
- create no order, payment, sourcing job or inventory;
- genuine offer availability emits an outbox event and governed in-app/SMS notification;
- processing is replay-safe and at most once per activation cycle;
- cancellation is idempotent;
- do not claim push without a real push channel.

## 12. K9.3 — Support and concierge requests

Create one customer-request domain.

Suggested model:

- identity_id and household_id;
- request_type: support or concierge_sourcing;
- optional order_id and offer_id;
- optional product_query_fa;
- message_fa;
- contact_preference: in_app or sms;
- status: submitted, in_review, resolved or closed;
- timestamps.

Customer endpoints:

    POST /api/v1/customer-requests
    GET  /api/v1/customer-requests
    GET  /api/v1/customer-requests/{request_id}

Operator endpoints:

    GET  /api/v1/operator/customer-requests
    POST /api/v1/operator/customer-requests/{request_id}/status

Rules:

- creation requires idempotency key;
- validate referenced ownership;
- promise no availability, refund, replacement, response time or sourcing success;
- concierge requests do not automatically create catalog items;
- audit all status changes;
- bound and safely render messages.

## 13. K9.3 — Journey delivery and check-ins

Keep JourneyDefinition.content JSONB if desired, but validate a versioned approved schema containing:

- neutral title/summary;
- eligibility facts;
- finite duration/window;
- ordered steps/check-ins;
- allowed answers;
- completion requirements;
- exception behavior;
- Garden object key/eligibility result;
- professional approval metadata reference.

Add:

    GET  /api/v1/pet-life/pets/{pet_id}/journey-offers
    GET  /api/v1/pet-life/journey-definitions/{definition_id}
    GET  /api/v1/pet-life/journeys/{journey_id}
    POST /api/v1/pet-life/journeys/{journey_id}/check-ins

Add durable journey_check_ins with journey, step/check-in key, strictly validated answer, submitting identity, timestamp and idempotency/uniqueness.

Rules:

- deliver only approved, active, eligible definitions;
- starting remains explicit;
- accept check-ins only in valid active windows;
- pause/resume/stop remain respected;
- exceptions remain non-diagnostic;
- completion validates requirements server-side;
- one completion creates at most one diary memory and one Garden reward;
- retired/expired approval fails closed for new starts;
- active journeys retain immutable definition version subject to safety withdrawal.

## 14. K9.3 — Diary and Garden

Type diary list and add:

    GET /api/v1/pet-life/pets/{pet_id}/diary/{entry_id}

Return title, note, type, happened_at, source type, safe source reference and linked Garden object summary.

Return typed Garden state:

- pet ID and layout version;
- unlocked quadrants;
- visible slot rules/counts;
- objects with state, key, memory ID and coordinates;
- next eligibility facts/reason where safe.

Unlock/eligibility is server-derived from visible milestone rules, never XP.

Keep placement PUT and add:

    DELETE /api/v1/pet-life/garden/{reward_id}/placement

DELETE sets the existing reward state to stored, clears coordinates/placement timestamp and preserves object/memory. It is idempotent.

Keep openNextQuadrant as client navigation unless it truly represents persisted domain state. Prefer server-derived unlocked state.

## 15. Existing capabilities not to rebuild

K8 already implements these; preserve them and improve response typing only:

- OTP and access/refresh/logout sessions;
- household creation and address create/list;
- checkout and Zarinpal initiation/callback;
- sourcing, fulfillment, delivery and inventory projection;
- external inventory and inventory assignment/open/correct/exhaust;
- journey start/pause/resume/stop/complete;
- notification inbox/feed/read and SMS preference;
- wallet ledger/balance;
- progressive pet profile and breed selection/history/completeness;
- measurements, trends, reminders and safe comparison;
- consent, private assets and body assessments;
- approved breed knowledge and care guidance;
- privacy export/requests;
- operator knowledge governance, evidence, audit and webhook replay.

Do not create duplicate services or parallel tables.

## 16. Explicitly out of scope

Do not add or enable:

- reserve-now;
- customer self-service cancellation after sourcing commitment;
- executable refunds, replacements or substitutions;
- unapproved compensation promises;
- marketplace/seller onboarding, commissions or settlements;
- inferred breed or disease;
- unapproved medical content;
- XP, streaks, health scores, Garden decay or purchase rewards;
- client-authored prices, delivery promises or trust claims;
- push claims without a real push channel.

## 17. Persistence and migrations

Add ordered Alembic revisions after 20260716_0018 and keep one head.

Expected persistence:

- product nominal quantity/media;
- order-line pet plans;
- semantic remaining-input provenance/bounds;
- reorder snoozes;
- delay acknowledgements;
- availability subscriptions;
- customer requests;
- journey check-ins;
- default-household preference only if chosen.

Requirements:

- explicit foreign keys, checks, uniques and indexes;
- nullable/safe rollout for existing data;
- no destructive rewrite of financial/audit history;
- downgrade path where feasible;
- PostgreSQL migration rendering and one-head verification;
- concurrency-safe uniqueness/idempotency.

## 18. Errors, idempotency and pagination

Use the existing stable envelope:

    {
      "error": {
        "code": "stable_machine_code",
        "message": "safe message",
        "details": {},
        "request_id": "correlation-id"
      }
    }

Requirements:

- never expose raw provider/database errors;
- document stable codes per endpoint;
- require Idempotency-Key where replay could duplicate effects;
- same key with a different body conflicts;
- use bounded offset pages for history/admin lists;
- use signed opaque cursors for growing customer feeds.

## 19. Required acceptance scenarios

### K9-T1 — First-time bootstrap

OTP verify → context has no household → create household/pet/address → context returns deterministic default and completed onboarding.

### K9-T2 — Returning user

Fresh login on new device → context reconstructs household/pets without local UUIDs → pet switcher can load.

### K9-T3 — Commerce/payment

Offer detail exposes approved trust → checkout snapshots IRR → verified payment sets commitment → reload-safe order detail → one sourcing job.

### K9-T4 — Order pet plan

Paid line planned for two pets → no estimate → delivery creates one unopened unit with two unknown-share assignments → no per-pet number.

### K9-T5 — Opening with known facts

Unopened unit → semantic/exact opening → known portion/share → typed estimate/provenance → justified pet range.

### K9-T6 — Unknown shares

Shared unit with unknown shares → household estimate or unknown only → no per-pet value anywhere.

### K9-T7 — External purchase

External product follows inventory, assignment, opening and estimation lifecycle where facts permit.

### K9-T8 — Reorder snooze

Server recommendation → 72-hour snooze → Today suppresses → early return only under documented worsening rule.

### K9-T9 — Availability

Unavailable offer → subscription returns order_created=false → no commercial records → availability creates one governed notification → replay creates no duplicate.

### K9-T10 — Delayed order

Existing in-transit order receives delay → journey shows original/revised timestamps → acknowledgement persists → no compensation/cancellation implication.

### K9-T11 — Journey/Garden

Approved offer → explicit start → valid check-ins → completion → one diary/reward → placement → storage → replacement, preserving memory.

### K9-T12 — Policy gates

Disabled reserve/refund/replacement/substitution/compensation capabilities are absent and non-executable.

### K9-T13 — Authorization

Cross-household access to all new/existing customer resources returns non-enumerating 404 with no side effect.

### K9-T14 — Concurrency/replay

Concurrent duplicate checkout, callback, subscription, request, acknowledgement, check-in and completion produce one canonical effect.

## 20. Verification

Run and report:

    ruff check .
    mypy app
    pytest
    alembic heads
    alembic upgrade head against PostgreSQL
    OpenAPI export and artifact comparison
    docker compose config --quiet

Add migration, API contract, authorization, idempotency, concurrency, policy, OpenAPI, Today union, no-estimate-before-opening, unknown-share leakage, notification replay, journey withdrawal and Garden reversibility tests.

Do not claim live provider, load, backup/restore or production certification unless genuinely exercised.

## 21. Required handoff

Return a complete source archive plus:

1. GATE_K9_PROGRESS.md.
2. BACKEND_FRONTEND_INTEGRATION_CONTRACT.md mapping UI intents to endpoints.
3. Updated BACKEND_SYSTEM_MAP.md.
4. Updated API_ENDPOINT_CATALOG.md.
5. Updated docs/api/frontend-integration.md.
6. Updated checked OpenAPI JSON.
7. Request/response examples for all new operations.
8. Alembic revisions/migration notes.
9. fixtures/demo/v2-frontend.json covering K9-T1 through K9-T11.
10. Test summary with exact commands/counts.
11. Policy decision register.
12. Changed-file manifest and exact revision.

## 22. Delivery checkpoints

Implement in order:

1. **K9.0:** policy flags, named schemas and OpenAPI foundation.
2. **K9.1:** context, pet list, offer detail/media, order detail and pet plan.
3. **K9.2:** rich inventory, semantic opening/correction, authoritative reorder, snooze and typed Today.
4. **K9.3:** subscriptions, customer requests, delay acknowledgement, journey delivery/check-ins, diary detail and Garden state/storage.
5. **K9.4:** cross-module acceptance, fixtures, documentation and packaging.

Stop for review after each checkpoint. Do not mix unresolved policy decisions with unrelated implementation.

## 23. Definition of done

K9 is complete only when:

- a returning user on a new device can discover household and pets;
- every approved frontend command is endpoint-backed or classified local/deferred;
- critical customer responses are strongly typed;
- frontend never invents price, delivery, trust, portion or policy facts;
- semantic opening avoids client-side gram guesses;
- incoming orders appear only for planned pets;
- unknown shares never leak per-pet estimates;
- subscription creates no order;
- snooze and delay acknowledgement are durable/idempotent;
- approved journeys can be discovered, read and checked in;
- diary and Garden detail/placement/storage are complete;
- disabled policy capabilities remain inaccessible;
- all automated checks pass;
- OpenAPI, docs, fixtures, migrations and archive agree on the same revision.

For each checkpoint report GO, POLICY BLOCKED or CONTRACT BLOCKED. “Implemented” without verification evidence is not sufficient.

