# Backend contract required before frontend integration

Mutable release facts and compatibility requirements are governed by
`backend/release-contract.json`.

The design package historically referenced a backend contract with:

- Alembic head, OpenAPI hash/counts, and policy defaults: see the canonical release contract
- Typed journey content/steps/answer options and typed reorder options

The authoritative OpenAPI file was not included in the designer ZIP. Therefore the coding agent must obtain it from the current backend repository or a running backend and verify it before generating client types.

Required typed schemas include:

- `JourneyContentResponse`
- `JourneyStepResponse`
- `JourneyAnswerOptionResponse`
- `JourneyCheckInBody`
- `ReorderOptionResponse`

Required journey discovery is expected under:

`GET /api/v1/pet-life/pets/{pet_id}/journey-offers`

All protected paths are expected under `/api/v1`. The runtime `PolicyResponse` is authoritative.

## Blocker rule

If the repository does not contain a matching or newer compatible OpenAPI contract, report:

`CONTRACT BLOCKED`

Include the observed migration head, OpenAPI hash, missing or changed operations/schemas, and the smallest backend action needed. Do not hand-write speculative DTOs and do not use the older generic journey/reorder structures.

If the backend is newer, use the newer contract, regenerate types, and document every design-impacting difference.
