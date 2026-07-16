# Pet Platform backend — system map and capability inventory

Snapshot: Gate K8, 2026-07-16

## 1. Product and operating model

The backend supports an Iran-first premium pet-nutrition platform in which commerce is the
acquisition wedge and the pet profile becomes the durable experience. The platform is the merchant
and operator; it is not an open marketplace. Products are sourced after full payment. Monetary
values are stored in IRR. The delivery commitment is exactly 366 hours. Reserve-now is modeled but
disabled until its payment, approval and customer-rights policy is finalized.

The core ownership boundary is the household. A household owns identities, addresses, orders,
wallet value and physical inventory. A pet owns its profile, consumption assignments, measurements,
journeys, diary and Persian Garden. An order is never treated as pet history merely because a pet was
optionally assigned to its product.

## 2. Runtime architecture

| Component | Responsibility | Authority |
|---|---|---|
| FastAPI API | Customer, operator and provider-facing HTTP contracts | Command/query boundary |
| PostgreSQL 17 | Financial, operational, pet-life, knowledge and audit records | System of record |
| Redis 7 | Coordination and transient worker support | Never authoritative |
| Outbox worker | Reliable asynchronous side effects and provider delivery | PostgreSQL outbox |
| Scheduler | Due work, review lifecycle and expiring obligations | PostgreSQL state |
| Filesystem storage | Private medical/body media and evidence | Persistent Docker volume |
| Alembic | Ordered database evolution | Head `20260716_0018` |
| OpenAPI | Checked frontend/backend contract | `docs/api/openapi.json` |

Local Compose services are `postgres`, `redis`, `migrate`, `api`, `worker`, and `scheduler`.
Persistent named volumes are `postgres_data`, `redis_data`, and `media_data`. Production uses the
same local-filesystem abstraction for media rather than S3.

## 3. Domain map

| Domain | Implemented capabilities |
|---|---|
| Identity | Iranian mobile normalization, OTP request/verification, access/refresh sessions, logout, throttling, session revocation |
| Household | Single-owner launch model, household membership, addresses, access checks, customer overview |
| Catalog and offers | Platform-owned catalog, supplier country, supplier assurance, shelf-life promise, reference-price evidence, capacity |
| Checkout | Full-payment order creation, capacity enforcement, idempotency, IRR-only policy |
| Payments | Zarinpal request/callback adapter, canonical payment attempt states, verified callback handling, reconciliation |
| Sourcing | Sourcing begins only after verified payment, line-level sourcing confirmation, exact sourced-unit expiry |
| Orders | Customer order feed, factual order journey, fulfillment transitions, delivery, delays and resolution boundary |
| Inventory | Household-owned purchased/external units, unopened/open/exhausted states, multi-pet assignment, unknown shares |
| Food estimation | Starts only after confirmed opening, estimate ranges, corrections, shared consumption, honest uncertainty |
| Replenishment | Pessimistic depletion range, latest promised delivery, safety buffer and transparent reorder assessment |
| Pets | Progressive profile, known/mixed/unknown breed selection, immutable selection history, optional completeness prompts |
| Today | Read-mostly pet hub combining utility, next event, journey, compact Garden and at most one quiet guidance item |
| Journeys | Operator-created and approved definitions; explicit start, pause, resume, stop and completion |
| Diary | Durable pet memories, including journey completion records |
| Persian Garden | Meaningful milestone rewards, placement and memory linkage; no purchase rewards, XP, streak or decay |
| Pet health | Immutable measurements/corrections, weight trend, reminders, provenance-aware reference comparison |
| Private pet assets | Purpose-specific consent, medical/body uploads, authenticated access, withdrawal and retention-aware removal |
| Body assessment | Owner-reported assessment plus separately evidenced operator/veterinary confirmation |
| Breed knowledge | Persian-normalized discovery, immutable imported releases, sources, claims, varieties and safe public views |
| Veterinary governance | Anonymous certified review, batch approval, evidence, expiry, withdrawal, re-review tasks and fail-closed publication |
| Benchmarks | Approved structured reference definitions; individual comparison only when explicitly allowed; non-diagnostic |
| Care guidance | Current-release approved guidance, breed/variety/explicit-age eligibility, provenance, dismiss/snooze/restore |
| Notifications | In-app inbox/feed, templates, SMS preference, quiet hours, queued/deferred/sent/failed/suppressed states |
| Wallet | IRR ledger, balance, late-credit capability and expiry model |
| Trust | Supplier assurance, reference-price evidence, protected evidence files and auditable claims |
| Privacy | Customer export, policy-gated requests, account disablement and active-session revocation |
| Operations | Single 360-degree operator, audit export, telemetry, webhook failure queue/replay, customer overview |
| Platform | Stable error envelope, request correlation, pagination/cursors, security headers, request-size bounds, health and metrics |

## 4. Critical state transitions

### Commerce and inventory

`offer → checkout → payment pending → payment verified → sourcing → movement → delivered → household inventory (unopened) → confirmed opening → estimate`

Payment does not create consumed inventory. Delivery does not start an estimate. Consumption begins
only after the owner confirms that the unit is open and supplies enough information for an estimate.

### Knowledge publication

`package validation → immutable import → certified review → activation preflight → approval → publish/supersede → eligible public content`

Expired or withdrawn approval fails closed. Imported content is never public merely because it was
accepted structurally. Activation and rollback are audited and replay-safe.

### Care and memory

`approved journey definition → explicit owner start → active/pause/resume/stop → completion → diary memory → eligible Garden reward`

Garden rewards come from meaningful milestones, not spending, app opens, repeated taps or passive
content reads.

## 5. External integration boundaries

| Provider | Current implementation | Production condition |
|---|---|---|
| Zarinpal | Port, adapter, initiation, callback and reconciliation workflow | Requires merchant credentials and provider certification |
| Payamak Panel | Port and adapter derived from supplied provider mechanics; backend generates and validates OTP | Requires live credentials, sender and delivery certification |
| Media storage | Normal filesystem directories behind a storage port | Persistent mounted Docker volume, backup and restore required |

Provider payloads are normalized at the integration boundary. Webhook processing is idempotent and
failed verified events can be replayed only through an audited operator action.

## 6. Safety and trust guardrails

- Customer wording is supplier-verified, not platform-guaranteed authenticity.
- Supplier country may be disclosed while supplier identity remains private.
- Before payment, offers expose a minimum remaining shelf-life guarantee; exact expiry follows
  sourcing confirmation.
- The default minimum remaining shelf life is six months at delivery unless an explicit exception is
  defined and disclosed.
- Reference-price comparisons require review date and retained evidence.
- Pet measurements, photographs, behavior and purchases never infer breed or disease.
- Health benchmarks and guidance are non-diagnostic and provenance-bearing.
- Exact transition/clinical content must be professionally approved before customer exposure.
- Private media requires purpose-specific consent and household authorization.
- Logistics and money remain factual and are never represented as a game metaphor.

## 7. Repository map

| Path | Contents |
|---|---|
| `app/api/routes` | HTTP endpoints grouped by authentication, commerce, operator, pet life, health, knowledge and privacy |
| `app/modules` | Domain models and services |
| `app/integrations` | Payment, OTP, notifications and filesystem ports/adapters |
| `app/workers` | Outbox and scheduler processes |
| `app/system` | Middleware and cross-cutting runtime behavior |
| `migrations/versions` | Alembic revisions `0001` through `0018` |
| `tests` | Unit, API, architecture and contract checks |
| `docs/api/openapi.json` | Checked machine-readable API contract |
| `docs/architecture` | Domain decisions and safety boundaries |
| `docs/runbooks` | Launch, deployment, observability and provider certification |
| `fixtures` | Deterministic non-production client/demo data |

## 8. Verification status

At this snapshot, Ruff and Mypy pass, all 83 automated tests pass, the checked OpenAPI artifact
matches the application, Alembic reports one head (`20260716_0018`), and the complete PostgreSQL
static migration chain renders successfully.

Live PostgreSQL/Redis Compose execution was explicitly deferred and must not be inferred from these
results. Zarinpal and SMS production certification remain dependent on live credentials. Security,
load, backup/restore and complete cross-module staging acceptance are launch gates, not completed
evidence.

## 9. Remaining implementation sequence

1. K9 — end-to-end cross-module application acceptance.
2. K10 — live Zarinpal and SMS-provider certification.
3. K11 — PostgreSQL, Redis, worker, scheduler, migration and persistent-volume certification.
4. K12 — security, upload, backup/restore, load and incident hardening.
5. K13 — frontend contract integration and approved UX acceptance paths.
6. K14 — Iran-first staging, operational policy closure and launch rehearsal.

