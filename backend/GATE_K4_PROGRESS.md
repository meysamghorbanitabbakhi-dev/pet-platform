# Gate K4 — structured benchmark capability

## Delivered

- Immutable benchmark definitions bound to approved, published claims and their checksum.
- Weight and height-at-withers references with strict unit pairing.
- Registry, population and growth reference purposes.
- Age, life-stage, sex, neuter, breed, variety and geography applicability metadata.
- Explicit `comparison_allowed` gate.
- Registry conformation ranges technically prevented from classifying pets.
- Authenticated measurement-to-reference comparison endpoint.
- Mixed-breed, imprecise-age, unit and scope fail-closed behavior.
- Dataset/claim provenance and Persian non-diagnostic disclaimer in every response.
- Migration revision `20260716_0014` and updated OpenAPI contract.

## Important operational condition

The veterinarian's real-world approval must still be entered through the K2 checksum-and-evidence
workflow. K4 does not translate a verbal or off-platform statement into database approval. After
the collector returns the corrected canonical bundle, it can be imported, reviewed, published and
then used to register eligible benchmark definitions.

## Deferred environment evidence

Live Docker Compose PostgreSQL/Redis testing remains deferred by project direction. This slice
requires lint, static typing, unit/contract tests, one Alembic head and complete offline PostgreSQL
migration rendering. Live constraints and concurrent operator writes remain part of later
environment certification.
