# Gate B0 handoff

**Status:** Code foundation complete; container runtime verification pending on a Docker host  
**Date:** 2026-07-16

## Delivered

- FastAPI modular-monolith repository structure.
- PostgreSQL/SQLAlchemy/Alembic foundation with one migration head.
- Redis worker and single-leader scheduler entry points.
- Persistent filesystem media adapter with atomic writes and traversal protection.
- Customer/operator identity tables and Iranian mobile normalization.
- Transactional outbox dispatcher with claim, retry, and idempotent-consumer expectation.
- Webhook inbox, request idempotency claims, and operator audit foundation.
- Request IDs, liveness, readiness, and locked-policy API.
- Payment and OTP provider ports with no provider SDK leakage into domain code.
- First-class launch module namespaces for household, pets, commerce, sourcing, inventory,
  food estimation, replenishment, Journeys, Diary, Persian Garden, wallet, and notifications.
- Docker Compose services for PostgreSQL, Redis, migration, API, worker, and scheduler.
- Architecture decisions and local/backup runbooks.

## Founder-approved policies enforced in configuration

- integer IRR;
- 366-hour commitment from verified payment;
- 5% late compensation;
- three-month wallet-credit expiry;
- earliest-expiry-first wallet consumption;
- filesystem media storage;
- full payment only;
- `Reserve now` disabled;
- sourcing starts only on evidenced supplier financial commitment.

## Verification evidence

- Ruff: clean.
- Mypy strict: clean.
- Pytest: 23 passed.
- Python compile/import: passed.
- API smoke: liveness and policy endpoints returned HTTP 200 from Uvicorn.
- Alembic: exactly one head; offline PostgreSQL upgrade SQL generated successfully.
- Compose document: parsed and required services/volumes verified statically.

## Environmental limitation

Docker is not installed in the current execution environment. PostgreSQL/Redis containers,
the live migration, persistent named volumes, and the full readiness endpoint were therefore
not executed here. Run the local-development checklist on a Docker host before declaring the
container portion of Gate B0 closed.

## Gate B1 entry

Gate B1 implements the first paid-commerce vertical slice:

`household → optional pet → catalog/trust → full-payment offer → cart → checkout snapshot →
payment verification → paid order → 366-hour commitment`

Payment and OTP provider names/contracts are required before concrete adapters are added.
