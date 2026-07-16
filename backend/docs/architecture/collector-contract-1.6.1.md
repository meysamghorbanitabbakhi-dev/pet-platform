# Collector contract 1.6.1 integration

## Verified package

Run:

```bash
python -m app.cli.validate_knowledge_package /path/to/package.zip
```

The validator rejects unsafe ZIP paths, missing or unlisted governed files, byte-length or SHA-256
mismatches, an invalid release checksum, and a canonical bundle that fails backend validation. It
returns both the collector release checksum and the backend canonical bundle checksum because they
protect different representations.

The accepted final package contains 141 breeds/groups, 4 varieties, 150 sources, 906 claims and
705 independently governed guidance records. `retrieval_date` is accepted as the collector's
canonical source field while the legacy `retrieved_at` alias remains compatible.

## Import and approval sequence

1. Verify the complete ZIP offline.
2. Upload the approval document as private operator evidence.
3. Import `backend-import-bundle.fa.json`; all claims are forced non-public.
4. Import `care-guidance.fa.json`; all guidance is independently forced non-public.
5. Record batch approval with the canonical release checksum, evidence ID, review dates and
   `credential_verified_privately=true`.
6. Publish the release using the same certified-review requirement.
7. Materialize structured quantitative registry references.
8. Inspect the reconciliation report before enabling the client release.

The reviewer remains customer-anonymous. The platform records only that credentials were verified
privately, the evidence reference, exact checksums, decision, dates and limitations.

## Guidance independence

Guidance is not flattened into ordinary claims. It has its own immutable source record, supporting
claim IDs, review status, eligibility, review checksum and expiry behavior. Claim approval does not
implicitly approve guidance; the batch workflow records a separate review for every guidance item.

Public responses expose only approved eligible guidance, its domain, Persian text and supporting
claim IDs. Private evidence and reviewer identity never leave the operator boundary.

## Benchmark materialization

Materialization reads numeric ranges from structured breed/variety records and never parses Persian
display text. Only approved quantitative claims in the published release are candidates. Contract
1.6.1 marks all such values as registry-conformation references with comparison disabled, so the
result is displayable but cannot classify an individual animal.
