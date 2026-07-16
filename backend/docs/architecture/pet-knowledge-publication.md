# Pet knowledge review and publication

## Purpose

This slice turns an immutable imported Persian knowledge release into a controlled, reversible
public projection. Import is not approval. Publication requires a separate review decision bound
to the exact checksum of the reviewed content.

## Reviewer privacy

The public product does not identify the veterinarian. Review records use the fixed disclosure
`anonymous_external_veterinarian`; they store the review decision, evidence file, dates,
limitations, operator and reviewed checksum internally. No reviewer identity or credential is
returned by the public knowledge API.

Evidence files use the existing private-file controls and are not public assets. The platform
operator records the external decision but cannot silently change the reviewed content: a checksum
mismatch rejects the operation.

## State and approval rules

- Import creates an `imported` release and non-eligible claims.
- A claim review may approve or reject a claim only while its release is imported.
- Approval makes the exact claim `veterinary_approved` and app-eligible.
- Publication requires an exact release checksum, review evidence and at least one approved claim.
- Only one release may be `published` at a time.
- Replacing a published release requires explicit supersession.
- Claim and release withdrawal disable use without erasing evidence or history.
- Review dates and optional next-review dates are recorded. Automatic expiry enforcement is not
  part of this slice and must be added before expiry can change publication automatically.

## Public projection

`GET /api/v1/knowledge/breeds` returns the current published release metadata and safe breed
identity fields. `GET /api/v1/knowledge/breeds/{breed_id}` adds varieties and only claims that are
both veterinary-approved and app-eligible.

The API constructs responses from an allowlist. It never serializes raw imported records. Public
source citations may contain URL, DOI, PMID, publication and retrieval date; internal notes,
copyrighted excerpts, evidence-file details and reviewer data are excluded.

## Operational boundary

The single 360-degree operator performs the authenticated recording actions. The medical judgment
still belongs to the external veterinarian. Every review, publication and withdrawal creates an
operator audit event.

## Follow-up work

- Runtime PostgreSQL verification of the partial unique published-release index.
- Concurrency tests for simultaneous publish attempts.
- Scheduled handling of review expiry and re-review reminders.
- Product policy for whether withdrawal should retain a public tombstone or return not found.
