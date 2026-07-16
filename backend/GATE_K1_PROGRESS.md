# Gate K1 — Versioned breed-knowledge ingestion

## Delivered

- Persian-first versioned knowledge release model;
- separate normalized breeds, varieties, sources, claims and claim-source links;
- deterministic canonical JSON and SHA-256 release checksums;
- no-write validation endpoint and idempotent import endpoint;
- immutable raw release retained on approved filesystem storage;
- cross-reference, duplicate, review-state and nested-range validation;
- imported release counts and warnings;
- operator audit record for every import;
- database-enforced `app_eligible=false` for every ingested claim;
- deterministic demo knowledge bundle and integration documentation;
- migration `20260716_0011` and refreshed OpenAPI contract.

## Boundaries

- ingestion is not publication;
- submitted veterinary status is not treated as platform approval;
- no public breed or claim endpoint exists yet;
- no clinical rule consumes imported claims;
- no imported range affects individual pet interpretation;
- veterinary review/publication and release supersession are Gate K2.

## Verification

- Ruff passes.
- strict mypy passes across 121 source files.
- 65 tests pass.
- Alembic has one head at `20260716_0011`.
- Full offline PostgreSQL migration SQL renders.
