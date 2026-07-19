# Provenance-aware pet benchmarks

## Registration boundary

A benchmark definition can be recorded only from a claim that is veterinary-approved,
app-eligible and part of the current published release. The operator must supply the exact claim
checksum. One immutable definition is allowed per claim; corrected science requires a new claim
and release rather than silent mutation.

Every definition records measurement type and unit, reference purpose, numeric range, optional age
scope, life stage, sex and neuter scope, breed and optional variety, population geography,
measurement definition and explicit comparison permission.

## Reference is not classification

`registry_conformation` ranges can be displayed with provenance but can never classify an
individual pet. `population_reference` or `growth_reference` may classify only when
`comparison_allowed=true` was explicitly recorded after veterinary approval.

Possible calculation states are:

- `no_applicable_reference`: no current approved definition matches the measurement and breed;
- `not_applicable`: a definition exists but age, sex, neuter, variety, unit or breed does not fit;
- `reference_only`: the range may be displayed but comparison is not approved;
- `compared`: below, within or above the population reference, always non-diagnostic.

Mixed-breed pets are never classified through a single-breed reference. Age-scoped definitions
require an exact or month-precision birth date. Grams may be normalized to kilograms; other unit
guessing is prohibited.

## Customer response

The measurement comparison endpoint returns the exact dataset version, claim ID and Persian claim
text, reference purpose, population geography, measurement definition and range. It never returns
an “ideal weight,” diagnosis, disease risk, treatment or food quantity.

Every response carries the Persian disclaimer that the comparison is not a diagnosis or ideal
weight determination and should be considered with body condition and veterinary advice.
