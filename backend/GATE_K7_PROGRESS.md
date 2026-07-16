# Gate K7 — breed discovery and progressive profile enrichment

## Delivered

- Persian-normalized breed and alias search.
- Deterministic exact/prefix/contains relevance ranking.
- Species filtering and bounded results.
- Validated known-breed and variety selection.
- Explicit mixed and unknown selection modes.
- Immutable release-bound breed-selection history.
- Breed-identification provenance retained.
- Direct arbitrary breed assignment through profile patching blocked.
- Optional profile-completeness and next-prompt response.
- Migration `20260716_0017` and updated OpenAPI contract.

## Guardrails

- No breed inference from photographs, body measurements, behavior or purchases.
- A mixed pet is never forced into one breed benchmark.
- An unknown choice counts as a completed profile decision.
- Search uses only the current published release.
- Profile completeness is not a health score and does not gate commerce.

## Deferred environment evidence

Live PostgreSQL search behavior, indexing strategy and concurrent profile updates remain part of
the deferred Docker Compose certification. The initial 141-record release is intentionally small
enough for deterministic in-process ranking after one bounded release query; indexed search can be
introduced when catalogue size or observed latency justifies it.
