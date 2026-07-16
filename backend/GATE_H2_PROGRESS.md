# Gate H2 — Private assets, consent, and body assessment

## Delivered

- private pet-owned filesystem assets separated from trust evidence;
- explicit versioned consent for body photographs and medical records;
- one active consent per pet and purpose, enforced in PostgreSQL;
- consent withdrawal removes linked assets from active use;
- signature-checked JPEG, PNG and PDF uploads with bounded size;
- authorized household-only metadata listing and file download;
- soft removal pending approved medical-retention policy;
- WSAVA-style 1–9 BCS storage, separate MCS and structured guided answers;
- top/side/supporting photo links with category validation;
- owner-reported assessment provenance;
- operator-recorded external veterinary confirmation requiring evidence and audit reason;
- health assets, consent and assessment data included in privacy export;
- migration `20260716_0010` and refreshed OpenAPI contract.

## Safety boundaries

- assets are never publicly addressed and storage keys are never returned;
- consent purpose must match asset category;
- withdrawn or removed assets cannot be downloaded;
- file extension and declared MIME type alone are not trusted;
- BCS/MCS data is recorded without diagnosis or treatment advice;
- operator records veterinary confirmation but is not represented as the clinical approver;
- physical deletion remains policy-gated because backups and legal retention are unresolved.

## Verification

- Ruff passes.
- strict mypy passes across 117 source files.
- 62 tests pass.
- Alembic has one head at `20260716_0010`.
- Full offline PostgreSQL migration SQL renders.
