# Gate K2 — anonymous veterinary review and safe publication

## Delivered

- Claim-level anonymous external veterinary approve/reject workflow.
- Release-level review and publication bound to immutable checksums.
- Evidence-file requirement, limitations, review dates and optional next-review date.
- Exactly one published release at the schema level, with explicit supersession.
- Audited claim and release withdrawal.
- Public Persian breed list/detail endpoints using allowlisted projections.
- Raw records, internal notes, copyrighted excerpts, evidence and reviewer details excluded.
- OpenAPI contract and migration revision `20260716_0012`.

## Verification

- Ruff: passed.
- Mypy: passed for 122 source files.
- Pytest: 66 tests passed.
- Alembic: one head at `20260716_0012`.
- PostgreSQL offline SQL render: passed for all migrations through `0012`.

## Explicitly deferred

Per project direction, Docker Compose PostgreSQL/Redis runtime tests are treated as a later
environment-certification activity, not as evidence collected here. This includes live migration,
partial-index enforcement and concurrent publication tests.

Automatic expiry enforcement is also not included. `next_review_at` is stored now so a later
scheduler slice can implement reminders and withdrawal/re-review policy without changing the
review record shape.
