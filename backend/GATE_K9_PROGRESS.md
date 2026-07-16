# Gate K9 progress

Base revision: `1da656bcd5e08310596a5c77e5cad4f421e74691`

Status: K9 implementation is complete through K9.4. Release remains policy-blocked where product approval is intentionally absent.

## Checkpoints

| Checkpoint | Result | Notes |
|---|---|---|
| K9.0 | GO / POLICY BLOCKED | Typed contracts, IRR money, policy flags and OpenAPI drift checks are present. Unresolved policy defaults fail closed. |
| K9.1 | GO | Context, catalog detail, order detail, pet plans and delivery-to-unopened inventory are present. |
| K9.2 | GO / POLICY BLOCKED | Inventory detail, exact-grams opening, estimates, authoritative reorder, snooze and typed Today are present. Semantic level bounds and safety buffer remain policy-blocked. |
| K9.3 | GO / POLICY BLOCKED | Availability subscriptions, customer requests, delay acknowledgement, journey check-ins, diary detail and Garden state/storage are present. Care journey delivery remains disabled by default. |
| K9.4 | GO | Acceptance scenario coverage, fixture, documentation reconciliation and archive packaging are present. |

## Acceptance scenario coverage

| Scenario | Automated evidence |
|---|---|
| K9-T1 | `tests/unit/test_k9_4_acceptance.py` validates bootstrap chain in `fixtures/demo/v2-frontend.json`. |
| K9-T2 | Fixture validates new-device context and pet switcher chain. |
| K9-T3 | Fixture validates offer detail to checkout, payment, reload-safe order and sourcing chain. |
| K9-T4 | Fixture validates pet planning to unopened unknown-share inventory with no estimate. |
| K9-T5 | Fixture plus K9.2 tests validate exact-grams opening and known-fact estimate behavior. |
| K9-T6 | Fixture plus K9.2 tests validate unknown-share household-only output. |
| K9-T7 | Fixture validates external inventory lifecycle. |
| K9-T8 | Fixture plus K9.2 tests validate reorder assessment, 72-hour snooze and Today suppression contract. |
| K9-T9 | Fixture plus K9.3 tests validate subscription no-commercial-record behavior and notification replay. |
| K9-T10 | Fixture validates delayed order journey and idempotent acknowledgement with no compensation implication. |
| K9-T11 | Fixture plus K9.3 tests validate approved journey, check-ins, one diary/reward and Garden storage. |
| K9-T12 | `test_k9_t12_policy_gates_are_disabled_and_non_executable` validates disabled policy gates. |
| K9-T13 | `test_k9_t13_cross_household_resources_have_authorization_surfaces` validates non-enumerating 404 surfaces. |
| K9-T14 | `test_k9_t14_replay_sensitive_operations_expose_idempotency_or_unique_effects` validates replay contracts. |

Frontend intent audit: zero unexplained intents. Every approved intent is classified as endpoint-backed, frontend-local, policy-gated or deferred in `fixtures/demo/v2-frontend.json` and `BACKEND_FRONTEND_INTEGRATION_CONTRACT.md`.

## Dirty-worktree manifest

Generated during K9.4 from a clean base. Changed-file manifest is maintained in `K9_CHANGED_FILE_MANIFEST.md`.

## Verification summary

Final command counts are recorded after execution in `docs/api/k9-test-summary.md`.
