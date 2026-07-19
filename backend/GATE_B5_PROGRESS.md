# Gate B5 — Communications and Trust Evidence

## Implemented

- Transactional SMS is separate from OTP authentication while reusing the Payamak transport.
- Customer preferences support per-event SMS enablement and optional Iran-local quiet hours.
- Notification templates are versioned, optionally active, and placeholder-validated.
- Outbox handlers enqueue late-credit notifications idempotently.
- Scheduler delivery records every attempt and applies bounded exponential retry.
- Preference changes are checked again immediately before delivery.
- Supplier assurance is an auditable, versioned evidence record backed by a local stored file.
- Offers require active supplier assurance before publication.
- Customer trust wording is represented as `supplier_verified`, never `100% authentic`.
- Reference prices require dated internal evidence and update the customer review date.
- Offers disclose a default six-month minimum remaining shelf-life guarantee.
- Sourced-unit evidence records exact expiry before delivery and links to the supplier assurance.
- Delivery is blocked until every order line has sourced-unit evidence.
- Exact expiry, supplier country, and authenticity basis are snapshot into household inventory.
- Migration `20260716_0006` is the sole Alembic head.

## Deferred by founder instruction

- Docker Compose PostgreSQL/Redis runtime and concurrency validation.

## Next slice

- Authenticated filesystem evidence upload and download endpoints.
- Customer addresses and delivery-contact snapshots.
- Offer availability windows and sourcing capacity controls.
- Notification inbox and read-state API.
- Operational metrics, health telemetry, and audit export.
