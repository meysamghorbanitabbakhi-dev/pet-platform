# Pet knowledge ingestion

The authored Persian JSON bundle is the source artifact; PostgreSQL stores an immutable normalized
release projection. Import never publishes content. The original canonical JSON is retained on the
approved filesystem volume under its SHA-256 checksum.

## Bundle contract

Top-level fields are `schema_version`, `dataset_version`, `language`, `breeds`, `varieties`,
`sources`, and `claims`. Language must be `fa-IR`. Persian is authoritative prose while canonical
English names, registry identifiers, DOI/PMID and controlled codes remain available for matching.

Each breed requires `id`, `species`, `name_fa`, and `name_en`. Each variety references a breed.
Each source requires `id`, `type`, and `title`; missing retrieval dates are warned. Each claim
references a breed, optional same-breed variety, one or more sources, Persian text, claim type and
review status.

Validation rejects duplicate IDs, orphan references, variety/breed mismatches, duplicated claim
sources, unsupported review states, reversed/negative ranges and clinical claims without evidence.
Dry-run validation computes the exact checksum and counts without storage or database writes.

## Trust boundary

Submitted approval metadata is imported as historical authored data, not trusted publication
authority. Every normalized claim is forced to `app_eligible=false`, backed by a database check.
Veterinary review and release publication require a later workflow. Reviewer public anonymity can
be preserved there without removing internal evidence of a completed professional review.
