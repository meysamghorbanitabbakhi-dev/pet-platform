# Production deployment profile

The application is provider-neutral and supports Iran-hosted PostgreSQL, Redis, ingress, monitoring,
and off-host backups. Customer media remains on the mounted filesystem volume. Do not replace it
with S3 without a new architecture decision.

Use `docker compose -f docker-compose.yml -f compose.production.yml config` to build the hardened
service definition. The production override removes direct API host-port publication; an approved
TLS reverse proxy/private load balancer must join the network and route traffic. Enable HSTS only
after HTTPS and all relevant subdomains are confirmed.

Required controls:

- secrets supplied by the infrastructure provider, never baked into images or compose files;
- encrypted PostgreSQL and media backups stored off the primary host;
- private PostgreSQL, Redis, worker, scheduler, and metrics connectivity;
- persistent media volume mounted only where application behavior requires it;
- one migration job per release, followed by API/worker/scheduler rollout;
- immutable image revision and recorded rollback target;
- Iran-local operational ownership and escalation contacts.

Capacity, replica counts, timeouts, RPO/RTO, and alert thresholds require measured traffic and
founder/infrastructure approval. This document deliberately does not invent them.
