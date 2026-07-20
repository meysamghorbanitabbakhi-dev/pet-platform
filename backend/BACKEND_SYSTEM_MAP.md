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
| Checkout/payment | Full-payment IRR checkout, Zarinpal initiation/callback, payment verification before sourcing and replay-safe checkout; payment/order row locks are never held across the Zarinpal `verify`/`inquiry` network call -- provider I/O runs unlocked, then a short, separately re-locked, replay-safe finalization transaction rechecks amount/currency/attempt-state/order-state and preserves exactly one sourcing job and one `order.payment_verified` event per order — hardened 2026-07-20 (Workstream 5C) |
| Orders | Reload-safe order detail, feed/journey, commitment fields, delay events, delay acknowledgement and pet planning |
| Sourcing/delivery | One sourcing path after payment; delivery projects sourced lines into unopened inventory without starting estimates |
| Inventory | Household inventory detail, external units, assignments, exact-grams opening, semantic-level bounds from nominal quantity and exhaust lifecycle |
| Food estimation | Server-owned ranges/provenance; unknown shares never leak pet-level remaining-days values |
| Replenishment | Authoritative reorder assessment, 3-day safety buffer and durable 72-hour snooze with approved early-break rule; system-proposed replenishment reservations (scheduler-created from pessimistic depletion estimate, customer approve/decline, one row per unit ever) gated behind `replenishment_reservation_enabled=false` — added 2026-07-19 (Workstream 3, ADR-009) |
| Outbox/scheduler | Every outbox-emitted event type is registered in `EVENT_REGISTRY` with a `handler`/`audit_only` disposition (no `unregistered` event types exist in practice); every `handler`-disposition event has a real handler wired in `app/workers/outbox.py`; operator-only `GET /operator/outbox/events?status=` and `POST /operator/outbox/events/{id}/replay` expose failed/dead-letter counts and a replay procedure (resets to `pending`, letting the normal poll loop redeliver it) — added 2026-07-20 (Workstream 5D) |
| KPI reporting | 19 versioned KPI definitions (`app/modules/reporting/kpi.py`) each documenting numerator/denominator/window/timezone(UTC)/currency/status-inclusion/late-event-handling/version/validation-query; read-only computation in `app/modules/reporting/service.py`; operator-only `GET /operator/kpis`/`GET /operator/kpis/{key}` (window_start/window_end); `margin` is registered but explicitly `computable=false` — no supplier cost field exists anywhere in the commerce schema, so it is not fabricated from `reference_price_irr` (a market-comparison price, not a cost); minimal operator dashboard at `/operator/kpis` — added 2026-07-20 (Workstream 6) |
| Today | Typed discriminated food states and deterministic single attention item with module failure isolation |
| Availability | Idempotent subscribe/cancel/list, order_created=false and once-per-activation governed notification |
| Support/concierge | Shared customer request domain, operator status workflow and no operational promises; verified concierge offer lifecycle (evidence-backed review, hybrid reference-price/landed-cost pricing, accept/decline/expire/refresh, operator-discretion catalog promotion) gated behind `concierge_offers_enabled=false` — added 2026-07-20 (Workstream 4, ADR-010) |
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

## 8. Frontend verification posture (Workstream 7, 2026-07-20)

An audit of the frontend against the K9 contract's hardening requirements (BFF-only browser calls, HTTP-only tokens, CSRF on every mutation, RTL, reduced-motion, focus management, mobile viewport, no internal-field leakage) found the infrastructure already correctly in place from prior K9/K10 work, with no gaps requiring a fix:

- **BFF-only**: no client component references `backendClient`, a backend env var, or an absolute-URL `fetch` anywhere — every backend call goes through `src/lib/api/backend.ts` (`import "server-only"`) and a `/api/bff/*` route.
- **HTTP-only tokens**: access/refresh cookies are `httpOnly: true`, `secure` in production, `sameSite: lax`, and `__Host-`-prefixed in production (`src/lib/session/server.ts`). The CSRF cookie is deliberately `httpOnly: false` (required for the double-submit pattern) but otherwise carries the same hardening.
- **CSRF**: every BFF route with a POST/PUT/PATCH/DELETE handler calls `requireCsrf` except `auth/otp/request` and `auth/otp/verify` — the pre-session login flow, where no session exists yet to have issued a token from (the standard, correct exemption).
- **No internal-field leakage**: no customer-facing frontend file references `supplier_id`, `supplier_cost`, `platform_margin`, `operator_note`, or `internal_name` anywhere.
- **RTL/reduced-motion/focus/viewport**: `<html lang="fa-IR" dir="rtl">` is set globally; `globals.css` has a `prefers-reduced-motion: reduce` rule and a `max-width: 360px` breakpoint; `Dialog`/`Sheet` share a `useFocusTrap` hook; `EmptyState`/`ErrorState` use `aria-live`/`role="alert"`.
- **Policy-hidden gating**: all three flag-gated features (reserve-now, replenishment reservations, concierge offers) gate their frontend queries behind the corresponding `policy.*_enabled` value rather than querying and showing a broken/error state when off.

**Not independently re-verified in this pass** (no visual browser access in this environment): actual keyboard-only tab-through, live screen-reader behavior, and visual rendering at 320-360px. Playwright + axe-core infrastructure exists (`tests/e2e/`, `chromium-320`/`390`/`768`/`1024` projects) but currently covers only 2 of the 11 customer journeys and uses a dev-fixture auth mode (`GATE_FIXTURE_MODE`) rather than a real backend — closing that out to "real-backend Playwright for all 11 journeys" plus axe-core/keyboard-flow tests for each is Workstream 8 scope, not yet done. The new `/operator/kpis` page (Workstream 6) was verified via typecheck, lint, production build, and backend integration tests proving its API is correct, but was not clicked through in a live browser and has no dev-fixture mock or E2E coverage yet -- said so explicitly here rather than claiming a browser check that did not happen.
