# Gate B6 — Platform Completeness

## Implemented

- Operator-authenticated evidence upload and download on persistent filesystem storage.
- Uploads are streamed with a 10 MB hard limit, media-type allowlist, safe filenames, SHA-256,
  size metadata, uploader identity, and audit record.
- Supplier assurance and reference-price evidence refer to registered evidence-file records.
- Households own reusable delivery addresses.
- Checkout validates address ownership and stores an immutable delivery-address snapshot.
- Offers support availability windows, capacity pause, and maximum pending sourcing quantity.
- Checkout evaluates capacity while holding the offer row lock.
- Public catalogue omits paused, not-yet-active, and expired offers.
- Transactional events create both an in-app notification and an independently controlled SMS.
- Customer notification inbox and idempotent read state are available.
- Operator telemetry covers outbox backlog, failed notifications, overdue orders, pending sourcing,
  and policy-blocked resolutions.
- Operator audit records can be exported as UTF-8 CSV, capped at 10,000 rows per request.
- Migration `20260716_0007` is the sole Alembic head.

## Deferred by founder instruction

- Docker Compose PostgreSQL/Redis runtime and concurrency validation.

## Next slice

- API contract hardening: pagination, consistent error envelopes, request schemas, and versioning.
- Privacy lifecycle: data export, account disablement, retention, and controlled deletion/anonymization.
- Backup/restore runbooks and operational recovery objectives.
- Seed/bootstrap command for the first operator and launch configuration.
- End-to-end acceptance fixtures and implementation handoff documentation.
