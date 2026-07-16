# Launch runbook

## Before deployment

1. Copy `.env.example` into the deployment secret manager and replace every placeholder.
2. Mount a persistent volume at `MEDIA_ROOT`; confirm the application user can write it.
3. Start PostgreSQL and Redis, then run `alembic upgrade head` exactly once.
4. Create the single operator with `python -m app.cli.bootstrap_operator --mobile 09...`.
5. Seed draft operational content with `python -m app.cli.seed_launch`.
6. The operator must review and activate notification content through the audited API.
7. Confirm Zarinpal and SMS credentials only when providers issue them. Until then, keep their
   adapters in non-production/test configuration.

## Acceptance checks

- `/health/live` is 200 and `/health/ready` confirms database, Redis, and storage.
- Policy output says IRR, 366 delivery-commitment hours, full payment, reserve disabled.
- OTP request and validation work with the real SMS provider.
- A sandbox payment can be requested, callback-verified, and reconciled idempotently.
- Paid order sourcing, delivery, inventory projection, bag opening, and estimate setup work.
- Delayed/unavailable flows expose no unapproved compensation or substitution policy.
- Customer export succeeds; disablement revokes sessions. Anonymization stays policy-gated.
- Backup and restore have been rehearsed against a disposable environment.

## Rollback

Stop new traffic, preserve database and media snapshots, deploy the previous application image,
and downgrade a migration only when its migration-specific data-loss impact has been reviewed.
Redis is disposable coordination state and is not the system of record.
