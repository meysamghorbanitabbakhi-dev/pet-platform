# Backup and restore runbook

This runbook intentionally requires explicit paths and manual review. Never restore into an
environment until the target database, media volume, and rollback plan have been identified.

## Back up PostgreSQL

Use `pg_dump --format=custom` from the PostgreSQL container and write the result to an explicit
host backup directory. Record the application version, Alembic revision, timestamp, and SHA-256
checksum beside the dump.

## Back up media

Archive the complete `media_data` volume during a write-controlled window. Record a SHA-256
checksum and keep its timestamp paired with the PostgreSQL dump. A database dump without its
corresponding media backup is not a complete platform backup.

## Restore rehearsal

1. Create a new empty PostgreSQL database and new empty media volume.
2. Restore the database dump with `pg_restore`.
3. Restore the paired media archive.
4. Run `alembic current` and confirm the expected revision.
5. Start one API instance against the restored environment.
6. Verify readiness, a private media authorization check, and representative audit/outbox rows.
7. Record duration and evidence; do not call the backup strategy verified until this succeeds.

## Production decisions still required

- encrypted off-host destination;
- retention schedule;
- recovery point objective;
- recovery time objective;
- who may initiate and approve a restore;
- media behavior when the primary host is lost.

## Rehearsal evidence (2026-07-20, Workstream 9)

Steps 1-4 above were rehearsed against the live dev-stack PostgreSQL container without touching
the shared database other tests depend on: `pg_dump --format=custom` (10.96 MB, 88 tables) into a
newly created, disposable `rehearsal_restore` database via `pg_restore`, then verified with direct
row/table counts rather than trusting a clean exit code alone -- table count (88), `orders_orders`
row count (5,674), and `alembic_version` (`20260720_0037`) all matched the source exactly. The
disposable database and dump file were dropped/removed immediately after.

**Not rehearsed in this pass**: the paired media-volume backup/restore (step 3), starting an API
instance against the restored database and exercising readiness/media-auth/audit checks (steps
5-6), and a host-loss/full-environment-recreation scenario. This dev sandbox has no configured
off-host destination, no media volume with representative content to make that rehearsal
meaningful, and no second environment to stand an API instance up against the restored data.
Genuine confidence in a full recovery still requires performing steps 3, 5, and 6 for real, ideally
against a copy of production-scale data, before relying on this runbook operationally.

## Rehearsal evidence (2026-07-20, gap-closure program Workstream 12)

Re-rehearsed steps 1-4 against the current schema (Alembic head `20260720_0042`, which added
row-level security -- see ADR-011's amendment -- since the prior rehearsal above at `20260720_0037`):
`pg_dump --format=custom` (88 tables) restored via `pg_restore --no-owner` into a fresh disposable
database in the same Postgres cluster. Table count (88), `orders_orders` row count (9,800), and
`alembic_version` all matched the source exactly, same as before. Additionally verified the parts
of this schema RLS added specifically: all 18 policies, all 3 helper functions
(`app_is_operator`/`app_household_ids`/`app_identity_id`), and both `relrowsecurity` and
`relforcerowsecurity` on a sample table (`orders_orders`) restored correctly and identically to the
source -- these are ordinary per-database schema objects, so a same-cluster `pg_dump`/`pg_restore`
carries them with no special handling needed.

**A genuine gap this surfaced, not present before Workstream 9**: the row-level-security feature
depends on a *role* (`database_app_url`'s `pet_platform_app`, created by migration `20260720_0040`)
that request traffic connects as. Roles are cluster-level objects in Postgres, never part of a
single database's `pg_dump` -- confirmed directly (`pg_restore -l`'s table of contents contains no
`CREATE ROLE`/role-grant entries at all). This rehearsal's restore worked because it ran against
the *same* Postgres cluster, where `pet_platform_app` already existed. **Restoring into a genuinely
fresh cluster (the real host-loss/disaster-recovery scenario, still not rehearsed here) requires
running `alembic upgrade head` far enough to recreate this role -- or an equivalent manual
`CREATE ROLE`/`GRANT` step -- before or immediately after the database restore, or the application
will be unable to authenticate to its own restored database at all.** This is now a required,
explicit step in any real disaster-recovery procedure for this platform, not an implicit assumption
the schema restore alone satisfies.

