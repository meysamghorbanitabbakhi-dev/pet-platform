# Local development runbook

## Start

1. Copy `.env.example` to `.env`.
2. Replace both development secret placeholders.
3. Run `docker compose up --build`.
4. Confirm `/health/live` and `/health/ready` return HTTP 200.
5. Confirm `alembic heads` reports exactly one head.

The `migrate` service must complete successfully before API, worker, or scheduler starts.

## Stop without deleting data

Run `docker compose down`. Do not add `--volumes` unless the persistent development data is
intentionally being destroyed.

## Diagnose

- API logs: `docker compose logs api`
- Worker logs: `docker compose logs worker`
- Scheduler logs: `docker compose logs scheduler`
- Migration logs: `docker compose logs migrate`
- PostgreSQL readiness: `docker compose exec postgres pg_isready -U pet_platform`
- Redis readiness: `docker compose exec redis redis-cli ping`

Redis may be cleared and rebuilt because it is not authoritative. PostgreSQL and `media_data`
must be protected together.

