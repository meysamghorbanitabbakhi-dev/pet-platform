# Pet knowledge lifecycle

## Review window

An approved claim or release may have `next_review_at`. The scheduler begins operator follow-up 14
days before that time and creates one durable task per review. Repeated scheduler runs are
idempotent. A newer approved review of the same target resolves the older task.

## Fail-closed expiry

At `next_review_at`, an approval without a newer replacement expires:

- a claim returns to `veterinary_review_required` and becomes non-eligible;
- a published release becomes `review_expired` and disappears from public selection;
- the original review and evidence remain immutable and auditable;
- the task remains visible as expired until a later reviewed release replaces it.

Expiry is not a medical conclusion and is never presented as a pet health state. It means only
that the platform no longer has a current approval for using that content.

## Version transitions

Publication still permits exactly one current release. A new publication explicitly names the
published release it supersedes. Public requests therefore resolve one coherent dataset version,
never a mixture assembled from unrelated releases.

An expired release cannot be silently revived. The operator imports and reviews a new immutable
release, then publishes it through the normal checksum-bound workflow.

## Pet-facing projection

`GET /api/v1/knowledge/pets/{pet_id}` requires household access. It uses the pet's recorded
`breed_reference_id`, confirms species consistency, and returns only approved eligible claims from
the current release. It also returns the breed-identification source so the client can communicate
owner-reported or professionally confirmed provenance honestly.

The endpoint does not produce diagnosis, risk scoring, expected weight, treatment, nutrition
quantities or medical recommendations. Every available response includes:

> این اطلاعات عمومی است و جایگزین نظر دامپزشک نیست.

Pets without a recorded breed receive a calm `breed_not_recorded` state and no inferred breed.
