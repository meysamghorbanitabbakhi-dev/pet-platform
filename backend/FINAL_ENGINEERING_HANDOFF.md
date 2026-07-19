# Engineering handoff

## System boundary

This is an Iran-first modular monolith for commerce, sourced-after-payment operations, household
inventory, pet life, journeys, diary, Persian Garden, order fulfillment, notifications, wallet,
trust evidence, privacy, and a single 360-degree operator.

Money is stored as integer IRR. Full payment is enabled. Reserve-now is modeled but disabled.
Delivery commitment is exactly 366 hours. Customer media/evidence uses ordinary filesystem
directories on a persistent Docker volume; S3 is not required.

## Deployment order

1. Configure secrets and persistent media path.
2. Start PostgreSQL and Redis.
3. Run `alembic upgrade head`.
4. Run operator bootstrap and launch fixture seed.
5. Start API and worker/scheduler processes.
6. Perform the checks in `docs/runbooks/launch.md`.

## Deliberate policy gates

- reserve-now payment and approval policy;
- cancellation, refund, replacement, and substitution rules;
- compensation amount/rule;
- professional approval of care content;
- privacy anonymization and retention matrix.

The backend does not convert these unresolved decisions into customer-facing claims.

## Evidence status

Static analysis, unit tests, API schema tests, and offline migration graph checks are automated.
Real Docker Compose PostgreSQL/Redis integration and concurrency testing was deferred by founder
instruction and must be run before production traffic; it is not represented as completed evidence.
