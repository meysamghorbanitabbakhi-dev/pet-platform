# Observability

`GET /internal/metrics` exposes Prometheus text counters for completed requests and accumulated
duration, labeled only by method, route template, and status. It deliberately excludes customer IDs,
phone numbers, raw URLs, payloads, and provider secrets. Production requires a 32+ character bearer
token via `METRICS_BEARER_TOKEN`; restrict the route at the private network layer as well.

Logs include the request ID. Alerting thresholds need real baseline traffic and must not be invented
before measurement. Initially monitor readiness failures, HTTP 5xx rate, payment reconciliation
backlog, failed notifications, overdue sourcing, and scheduler/worker liveness.

Use the operator telemetry endpoint for domain backlog facts. Prometheus metrics are process-local;
scrape every API replica and aggregate in the infrastructure provider.

## Redis-loss and worker/scheduler-restart behavior (rehearsed 2026-07-20, Workstream 9)

Rehearsed against the live dev stack, not just read from code:

- **Stopping the Redis container**: `GET /health/ready` correctly flips to `503` with
  `checks.redis: "unavailable"` (database and storage stay `"ready"`) within seconds -- an
  orchestrator's readiness probe would correctly stop routing traffic. Restarting Redis brings
  `/health/ready` back to `200`/all-`"ready"` within seconds, with no manual intervention or API
  process restart needed.
- **Restarting the worker and scheduler containers**: both come back up and log a clean start
  (`outbox worker started`, `scheduler started`). The worker's outbox-dispatcher heartbeat key
  (`pet-platform:outbox-worker:heartbeat`) resumes updating immediately. The scheduler's logs at
  restart time showed a `DeadlockDetectedError` on an unrelated identity-row query, which is
  expected noise from concurrent test-suite activity against the shared dev database at that
  moment (not a scheduler defect) -- it did not prevent the scheduler from starting cleanly
  afterward.

**Not rehearsed**: killing the API process itself mid-request, a full host loss, and behavior
under sustained (not momentary) Redis unavailability. Session auth itself does not depend on
Redis (`app/modules/identity/sessions.py` is JWT + PostgreSQL-backed, confirmed by inspection) --
Redis loss degrades readiness reporting and whatever else reads `app/core/redis.py` (rate
limiting, OTP challenge state) without blocking login/session validation, but that distinction
was checked by reading the code, not by exercising an OTP request during the outage.
