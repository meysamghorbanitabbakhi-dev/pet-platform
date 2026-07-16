# Gate B8 — Production readiness

## Delivered

- bounded `limit`/`offset` pagination with total and `has_more` on customer orders and inbox;
- low-cardinality Prometheus request counters and accumulated duration;
- production-protected internal metrics endpoint;
- correlated stable errors for HTTP, validation, and oversized requests;
- request-body limit and browser-facing security headers;
- optional HSTS, disabled until the HTTPS boundary is approved;
- hardened Compose production override;
- provider certification, deployment, and observability runbooks.

## Verification

- Ruff passes.
- strict mypy passes across 111 source files.
- 53 tests pass.
- Alembic remains one head at `20260716_0008`; no schema change was required.
- Full offline PostgreSQL migration SQL renders.

## Deferred production evidence

Compose PostgreSQL/Redis runtime and concurrency testing, restore rehearsal, provider certification,
TLS ingress validation, and infrastructure monitoring integration remain pre-production tasks. They
are not represented as completed evidence.
