# Gate K3 — knowledge lifecycle and pet-safe integration

## Delivered

- Scheduler-driven 14-day re-review task window.
- Idempotent one-task-per-review operator queue.
- Automatic resolution when a newer approval exists.
- Fail-closed claim and release expiry.
- Explicit `review_expired` release state.
- Authenticated, household-authorized pet knowledge endpoint.
- Species consistency check and breed-provenance disclosure.
- Persian non-diagnostic disclaimer and no breed inference.
- Migration revision `20260716_0013` and updated OpenAPI contract.

## Safety boundaries

- Review expiry is content governance, not a pet health signal.
- No expired content remains public or app-eligible.
- No knowledge claim is converted into diagnosis, treatment or benchmark advice.
- Reviewer identity and private evidence remain excluded from customer responses.
- A new immutable reviewed release is required after release expiry.

## Environment certification deferred

Per project direction, live Docker Compose PostgreSQL/Redis tests remain deferred. Offline
PostgreSQL migration rendering, unit/contract checks, lint and static typing are required for this
slice; live scheduler locking, `SKIP LOCKED` concurrency and partial-index enforcement must be
certified later in the target environment.
