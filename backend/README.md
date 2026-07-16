# Pet Platform Backend

Greenfield backend for the Iran-first pet platform. The codebase is a FastAPI modular
monolith with PostgreSQL, Redis workers, a scheduler, and filesystem media stored on a
persistent Docker volume.

## Locked launch policies

- Currency is integer IRR.
- The paid-order delivery commitment is exactly 366 hours.
- Late compensation is 5% of merchandise value and expires after three months.
- Wallet debits consume the earliest-expiring credit first.
- Full payment is enabled; `Reserve now` is modeled but disabled.
- Free cancellation ends only after evidenced supplier financial commitment.

## Local startup

```bash
cp .env.example .env
docker compose up --build
```

Endpoints:

- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/system/policies`
- `POST /api/v1/auth/otp/request`
- `POST /api/v1/auth/otp/verify`
- `POST /api/v1/auth/session/refresh`
- `POST /api/v1/auth/session/logout`
- `GET /api/v1/catalog/offers`
- `POST /api/v1/checkout/orders`
- `POST /api/v1/orders/{order_id}/payments/zarinpal`
- `GET /api/v1/payments/zarinpal/callback`

Zarinpal and Payamak Panel credentials are optional for local startup. Configure the
environment variables documented in `.env.example` when exercising provider calls. Zarinpal
sandbox mode is enabled by default; payment completion must still use server-side verification.

## Gate B1 transaction boundary

Checkout prices offers on the server and writes immutable order-line snapshots. Orders remain
`awaiting_payment` until Zarinpal verification succeeds. Successful verification is replay-safe,
sets the paid timestamp and exact 366-hour delivery commitment, and creates one sourcing job.
No sourcing job exists before verified full payment. Reserve-now remains modeled as a policy but
is disabled.

## Pet Life foundation

Households own inventory and pets receive consumption assignments from it. Delivery does not
start consumption: food estimation begins only after the owner explicitly opens a unit. Journey
content is versioned and must be approved before use. A legitimate journey completion creates a
durable diary entry and, at most once, an eligible Persian Garden object. Purchases, visits,
recap reads, repeated taps, and spending are not Garden reward sources.

## Operational control

Orders belong to households and move through explicit fulfillment states. Delivery records the
actual timestamp before projecting unopened inventory. Late delivery can create one 5% IRR
wallet credit per order, expiring after three calendar months; wallet debits consume the
earliest-expiring credit first. The Today endpoint is read-only by default and composes pet,
food, next-action, active-journey, and compact-Garden state.

The scheduler automatically detects overdue eligible orders and grants any missing late credit.
Customers receive a factual order timeline without internal operator notes. Refund, replacement,
and substitution proposals remain non-executable `awaiting_policy` records until an approved
policy version exists. Operator APIs provide a cross-domain customer overview for the single
360-degree platform operator.

Transactional notifications use versioned Persian templates, user preferences, Iran-local quiet
hours, recorded attempts, and bounded retry. Trust claims are evidence-backed: active supplier
assurance is required for an offer, reference-price support is dated and retained internally,
offers guarantee at least six months of shelf life by default, and sourced units expose exact
expiry before delivery. Delivery snapshots that evidence into household inventory.

Evidence uploads are operator-only, streamed into persistent filesystem storage, checksummed, and
audited. Household addresses are snapshotted immutably into orders. Offer availability and sourcing
capacity are enforced at checkout. Customers have a private in-app notification inbox, while the
operator has backlog telemetry and a capped UTF-8 audit export.

Launch hardening adds a stable error envelope with request correlation, bounded pagination,
authenticated customer export, policy-gated privacy requests, and audited account disablement that
revokes active sessions. Bootstrap the single operator with
`python -m app.cli.bootstrap_operator --mobile 09...`; seed draft launch content with
`python -m app.cli.seed_launch`. See `docs/runbooks/launch.md` before deployment.

Production readiness adds paged order/inbox collections, security headers and request-size limits,
plus low-cardinality Prometheus metrics at protected `/internal/metrics`. Use the hardened Compose
override and the deployment, observability, and provider-certification runbooks for staging/launch.

Frontend integration uses the checked `docs/api/openapi.json` contract. Growing order and inbox
collections also expose signed cursor feeds. Failed verified webhooks can be requeued only through
the audited operator API. `fixtures/demo/v1.json` provides deterministic Persian sample data for
client development without implying production product or policy facts.

The first pet-health slice adds progressive breed/variety provenance, immutable measurement and
correction history, personal weight trends, and measurement reminders. These are recorded facts and
calculations—not diagnoses or breed-based health judgments. Customer-written measurements are always
owner-reported until an evidenced professional ingestion path is introduced.

Private body photographs and medical documents now require versioned purpose-specific consent and
authenticated household access. BCS/MCS assessments remain owner-reported unless the operator records
external veterinary confirmation with credential details, evidence and an audited reason. Consent
withdrawal removes files from active use while physical deletion remains retention-policy-gated.

Persian breed knowledge can now be dry-run validated and imported as immutable checksummed release
snapshots. Breeds, varieties, sources and claims are normalized, but every ingested claim is forced
non-public. Ingestion never implies veterinary approval and cannot affect pet health interpretation.

Anonymous external veterinary review can now approve or reject an exact checksummed claim and
publish one reviewed knowledge release at a time. Review evidence and limitations remain internal;
public breed endpoints expose only allowlisted Persian identity fields, approved eligible claims,
and safe source citations. Releases and claims can be withdrawn without deleting their audit
history, and publication supersession is explicit.

The knowledge lifecycle scheduler now creates a single operator re-review task 14 days before an
approval is due. Expired approvals fail closed: a claim loses app eligibility, while an expired
release stops being public. Authenticated pet knowledge resolves only against the pet's recorded
breed in the current published release and always carries a non-diagnostic Persian disclaimer.

Approved quantitative claims can be registered as immutable benchmark definitions with explicit
purpose, population, age, sex, neuter, variety, unit and measurement-method context. Registry
conformation ranges are reference-only. Individual classification is possible only when the
approved definition separately permits comparison, and results remain non-diagnostic.

Collector contract `1.6.1` packages can be verified offline against their complete manifest before
import. The mapped bundle accepts the collector's `retrieval_date` convention. Independently
reviewed care guidance is stored separately from claims, while one evidence-backed certified and
anonymous veterinary batch decision can approve an imported release's claims and guidance. After
publication, structured registry ranges can be materialized idempotently as reference-only
benchmarks, with a reconciliation endpoint exposing stored and approved counts.

Knowledge activation runs coordinate preflight, certified batch approval, release supersession and
benchmark materialization as one audited transaction. Blocked runs can refresh preflight after
correction, completed execution is replay-safe, and rollback restores the prior release only while
its release-level veterinary approval remains current.

Breed discovery now searches Persian names and aliases with Persian/Arabic character normalization
and deterministic relevance ranking. Breed selection is validated against the current release and
records immutable history. Known, mixed and unknown states are explicit; the platform never infers
a breed from measurements, photographs or behavior. Profile-completeness prompts remain optional.

Personalized care guidance now resolves only independently approved items from the current
published release against a pet's explicit breed and variety selection. Today may show at most one
quiet, non-safety suggestion without changing its primary attention or creating a task. Owners can
dismiss, snooze or restore an exact guidance item; provenance, uncertainty and a non-diagnostic
disclaimer remain visible.

## Development checks

```bash
python -m pip install -e '.[dev]'
ruff check .
mypy app
pytest
docker compose config --quiet
```

## Boundaries

Domain modules own their writes. Cross-module changes use explicit commands or domain
events. Redis is never authoritative. Provider payloads enter through verified webhook
inbox records and canonical adapters. Financial and customer-policy changes are audited.
