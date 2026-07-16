# Gate K5 — collector 1.6.1 adaptation and batch approval

## Final package verification

- Collector release checksum: `9360e18141dc2db87399b1c4a17083fe3d380b84dc94518ce3582898e2a27409`
- Backend bundle checksum: `b7a9d142f546cf3022c162949f392e62cf5c63032209fc19a269a921d91c27d5`
- Breeds/groups: 141
- Varieties: 4
- Sources: 150
- Claims: 906
- Guidance: 705
- Manifest, file hashes, file set, canonical release checksum and backend bundle: passed
- Backend validation warnings: zero

## Delivered

- Safe ZIP/manifest validation CLI.
- Collector `retrieval_date` compatibility.
- Separate knowledge-guidance persistence and public projection.
- Independent guidance review and expiry lifecycle.
- Evidence-backed batch claim and guidance approval.
- Private certified-reviewer verification without public identity disclosure.
- Certified-review requirement on individual review and release publication.
- Idempotent structured benchmark materialization.
- Release reconciliation counts for claims, guidance and benchmarks.
- Migration `20260716_0015` and updated OpenAPI contract.

## Operational truth

The user confirmed that a certified veterinarian approved all content. The backend capability now
exists to record that approval correctly, but no production database was mutated in this local
slice. An operator must still upload the approval evidence and execute import, guidance import,
batch approval, publication and materialization against the target database.

Live Docker Compose PostgreSQL/Redis execution remains deferred by project direction. Offline
PostgreSQL migration rendering and all local static/unit/contract checks pass.
