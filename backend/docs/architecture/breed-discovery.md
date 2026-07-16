# Persian breed discovery and selection

## Search

`GET /api/v1/knowledge/search` searches only the current published release. It normalizes Arabic
and Persian forms of ی and ک, removes combining marks, treats the half-space as a word separator and
collapses whitespace. Ranking is deterministic:

1. exact Persian name;
2. exact Persian alias;
3. exact English internal name;
4. prefix matches in the same field order;
5. contained matches in the same field order.

Species filtering and a bounded result limit are supported. Results expose allowlisted identity
fields and aliases, not raw breed records or unpublished content.

## Selection

Customers explicitly choose one of three states:

- `known`: a breed and optional valid variety from the current release;
- `mixed`: no single breed reference is assigned;
- `unknown`: no breed is assigned and no inference is attempted.

Known selections must match the pet species. A variety must belong to its selected parent breed.
Identification provenance remains owner-reported, veterinarian-reported, registry-confirmed,
DNA-estimated or unknown.

Each choice creates an immutable selection-history record tied to the knowledge release used at
that moment. The current pet projection stores the explicit selection mode so an owner choosing
“unknown” is not repeatedly treated as someone who skipped the question.

Direct profile patching cannot modify breed fields. This prevents stale clients from writing an
arbitrary ID that bypasses current-release, species or variety validation.

## Progressive enrichment

Profile completeness reports whether birth date, sex, neuter status, breed state and a weight
measurement exist. It returns one optional next prompt and never blocks shopping or ordinary Today
use. Completion percentage is interface progress, not a pet health score.
