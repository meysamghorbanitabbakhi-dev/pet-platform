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

