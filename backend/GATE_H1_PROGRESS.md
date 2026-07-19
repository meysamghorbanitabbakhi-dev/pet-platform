# Gate H1 — Pet health foundation

## Delivered

- progressively expanded pet profile with breed/variety provenance;
- birth-date precision, sex, neuter state, expected adult size, mixed-breed and reproductive state;
- append-only longitudinal measurements with type-specific units;
- owner-reported provenance, method, confidence, notes and effective timestamp;
- correction lineage that preserves the original measurement;
- personal 7/30/90-day weight trends without population or diagnostic interpretation;
- scheduled measurement reminders with complete/dismiss states;
- health facts and reminder history added to authenticated privacy export;
- ninth linear Alembic migration and refreshed OpenAPI contract.

## Safety boundaries

- customer endpoints may only create owner-reported facts;
- veterinarian-reported and device-imported facts require future evidenced ingestion paths;
- corrections cannot change measurement type;
- breed ranges and health verdicts are not applied;
- unreviewed breed content is neither imported nor published;
- medical assets, BCS/MCS, care events and knowledge releases remain later gates.

## Verification

- Ruff passes.
- strict mypy passes across 116 source files.
- 59 tests pass.
- Alembic has one head at `20260716_0009`.
- Full offline PostgreSQL migration SQL renders.

Database-backed runtime/concurrency tests remain deferred under the existing founder instruction.
