# Pet Platform backend — system map and capability inventory

Historical Gate K9 snapshot — not current release authority. See `backend/release-contract.json`.

## 1. Product and operating model

The backend supports an Iran-first premium pet-nutrition platform where the household owns access, payment, orders, wallet value and physical inventory, while the pet owns experience, journeys, diary and Garden. The platform is the merchant/operator, not a marketplace. Products are sourced only after verified full payment. Money is integer IRR. Supplier identity is private.

K9 completes frontend integration contracts without resolving open product policy. Unapproved capabilities fail closed and remain hidden/non-executable.

## 2. Runtime architecture

| Component | Responsibility | Authority |
|---|---|---|
| FastAPI API | Customer, operator and provider-facing HTTP contracts | Command/query boundary |
| PostgreSQL | Financial, operational, pet-life, knowledge and audit records | System of record |
| Redis | Coordination and transient worker support | Never authoritative |
| Outbox worker | Reliable asynchronous side effects and provider delivery | PostgreSQL outbox |
| Scheduler | Due work and review lifecycle | PostgreSQL state |
| Filesystem storage | Private media/evidence storage abstraction | Persistent volume |
| Alembic | Ordered database evolution | Current head governed by the release contract |
| OpenAPI | Checked frontend/backend contract | `docs/api/openapi.json` |

## 3. Domain map

| Domain | Implemented capabilities through K9 |
|---|---|
| Identity/context | OTP/session lifecycle plus `GET /me/context` for new-device recovery, deterministic default household and onboarding flags |
| Household | Owner membership, addresses, active pet listing, non-enumerating household authorization |
| Catalog/offers | Typed offer detail with Persian content, IRR price, supplier country, verified trust, media, availability and hidden supplier identity; backend-owned Persian-normalized search (`/catalog/offers/search`); operator-curated, directed product alternatives with a read-time-revalidated public endpoint (`/catalog/products/{product_id}/alternatives`) — added 2026-07-19 to close G5-SHOP-13/14 |
| Checkout/payment | Full-payment IRR checkout, Zarinpal initiation/callback, payment verification before sourcing and replay-safe checkout |
| Orders | Reload-safe order detail, feed/journey, commitment fields, delay events, delay acknowledgement and pet planning |
| Sourcing/delivery | One sourcing path after payment; delivery projects sourced lines into unopened inventory without starting estimates |
| Inventory | Household inventory detail, external units, assignments, exact-grams opening, semantic-level bounds from nominal quantity and exhaust lifecycle |
| Food estimation | Server-owned ranges/provenance; unknown shares never leak pet-level remaining-days values |
| Replenishment | Authoritative reorder assessment, 3-day safety buffer and durable 72-hour snooze with approved early-break rule; system-proposed replenishment reservations (scheduler-created from pessimistic depletion estimate, customer approve/decline, one row per unit ever) gated behind `replenishment_reservation_enabled=false` — added 2026-07-19 (Workstream 3, ADR-009) |
| Today | Typed discriminated food states and deterministic single attention item with module failure isolation |
| Availability | Idempotent subscribe/cancel/list, order_created=false and once-per-activation governed notification |
| Support/concierge | Shared customer request domain, operator status workflow and no operational promises |
| Journeys | Approved versioned definitions, explicit start, detail, check-ins, server-side completion and safety withdrawal boundary |
| Diary/Garden | Typed diary detail, server-derived Garden state, placement and idempotent storage preserving memory |
| Policies | Reserve, cancellation, refund, replacement, substitution, compensation, care delivery approval and push remain gated; semantic bounds and reorder buffer are MVP-approved |
| Knowledge/health/privacy/ops | K8 capabilities preserved and exposed through existing contracts |

## 4. Critical state transitions

Commerce and inventory:

`offer → checkout → payment pending → payment verified → sourcing → delivered → household inventory (unopened) → confirmed opening → estimate`

Planning pets on an order never opens inventory or creates estimates. Delivery creates unopened inventory and copies planned pets as unknown-share assignments.

Care and memory:

`approved journey definition → explicit start → validated check-ins → completion → one diary memory → one Garden reward → placement/storage`

Garden rewards are meaningful server milestones only. There is no XP, streak, decay or purchase reward.

## 5. External integration boundaries

| Provider | Current implementation | Production condition |
|---|---|---|
| Zarinpal | Port, adapter, initiation, callback and reconciliation workflow | Requires live credentials and provider certification |
| Payamak Panel | Port and adapter; backend generates and validates OTP | Requires live credentials, sender and delivery certification |
| Media storage | Local filesystem storage port | Requires persistent volume and backup/restore validation |

## 6. Repository map

| Path | Contents |
|---|---|
| `app/api/routes` | HTTP endpoints grouped by auth, commerce, customer requests, operator, pet life, health, knowledge, privacy and system |
| `app/modules` | Domain models/services for identity, commerce, inventory, journeys, support, notifications and governance |
| `migrations/versions` | Alembic revision history; current head is governed by the release contract |
| `tests` | Unit/API/contract/K9 acceptance checks |
| `fixtures/demo/v2-frontend.json` | Deterministic K9-T1–T11 frontend demo fixture |
| `docs/api/openapi.json` | Checked OpenAPI artifact |
| `docs/api/examples.json` | Request/response examples for K9 operations |
| `docs/adr/ADR-004-k9-policy-boundaries.md` | Policy decision register |

## 7. Verification posture

K9.4 verifies static/type/test/OpenAPI/Alembic/archive consistency and records environment-blocked PostgreSQL/Compose checks when no safe runtime is available. Live provider certification, load, backup/restore and production launch rehearsal remain outside K9.
