# Gate K6 — resumable release activation

## Delivered

- Durable one-run-per-release activation state.
- Dry-run preflight with hard blockers and exact expected counts.
- Refreshable preflight after corrections.
- Evidence and checksum retained on the activation record.
- Atomic certified approval of claims, guidance and release.
- Atomic release supersession/publication and benchmark materialization.
- Replay-safe completed execution.
- Guarded rollback with prior-review validity check.
- Withdrawal of rolled-back claims, guidance and benchmarks.
- Operator audit events for preflight, execution and rollback.
- Migration `20260716_0016` and updated OpenAPI contract.

## Collector 1.6.1 activation inputs

- Claims: 906, enforced against the imported release count.
- Guidance: expected 705.
- Benchmark candidates: expected 101.
- Backend bundle checksum:
  `b7a9d142f546cf3022c162949f392e62cf5c63032209fc19a269a921d91c27d5`.
- Certified reviewer credentials must be verified privately.
- Approval evidence must already exist in private filesystem-backed evidence storage.

## Deferred environment evidence

No target database activation was performed. Live PostgreSQL row locking, transaction visibility,
partial unique-index behavior and Redis scheduler coexistence remain deferred with the wider Docker
Compose certification. Offline migration rendering and local checks are required for this gate.
