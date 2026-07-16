# Gate K8 — personalized care-guidance delivery

## Delivered

- Current-release, veterinary-approved care-guidance eligibility.
- Exact known-breed and variety matching.
- Explicit age-range filtering without invented life-stage thresholds.
- Bounded per-pet care-guidance feed with domain filtering.
- At most one quiet Today suggestion from non-safety domains.
- Release, checksum, source-claim and review provenance in public responses.
- Owner dismiss, snooze and restore preferences for exact guidance items.
- Migration `20260716_0018` and updated OpenAPI contract.

## Guardrails

- Mixed and unknown pets receive no breed-specific guidance.
- An absent birth date fails closed for explicitly age-scoped content.
- Today guidance never becomes primary attention or creates a task, streak or Garden reward.
- Safety content is not injected into Today as a casual suggestion.
- No diagnosis, treatment, individual health classification or breed inference.
- Preferences do not suppress newly reviewed replacement content automatically.

## Deferred environment evidence

Live PostgreSQL migration execution, row-lock behavior and Redis/Compose integration remain part of
the explicitly deferred Docker Compose certification. Static migration generation, application
tests and the checked API contract cover this slice without claiming those runtime checks passed.
