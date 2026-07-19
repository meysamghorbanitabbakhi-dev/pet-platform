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
