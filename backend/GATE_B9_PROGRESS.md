# Gate B9 — Frontend and integration readiness

## Delivered

- deterministic checked OpenAPI artifact and export command;
- frontend integration guide and concrete response examples;
- signed cursor codec resistant to client tampering;
- cursor feeds for customer orders and in-app notifications;
- existing bounded offset endpoints preserved for compatibility;
- operator-only failed-webhook queue and audited replay request;
- replay forbidden for rejected, unverified, or non-failed events;
- versioned deterministic Persian demo scenario.

## Verification

- Ruff passes.
- strict mypy passes across 113 source files.
- 56 tests pass.
- OpenAPI artifact contains the new feed and replay contracts.
- Alembic remains one head at `20260716_0008`; no schema change was required.
- Full offline PostgreSQL migration SQL renders.

## Deferred evidence

Database-backed cursor concurrency, actual webhook consumer replay, Compose services, real Zarinpal
and SMS certification, and frontend-generated client compilation remain staging tasks. They are not
represented as completed evidence.
