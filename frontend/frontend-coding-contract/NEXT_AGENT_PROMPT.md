# First prompt for the frontend coding agent

You are implementing Gate 5.2D-A of the Pet Platform frontend. Work inside the frontend repository you are given and preserve its approved stack, conventions, package manager, linting, testing, and deployment structure.

Read these files first, in order:

1. `README.md`
2. `BACKEND_CONTRACT_REQUIRED.md`
3. `ACCEPTED_PAGE_REGISTER.md`
4. `design-pages/gate5.2c-design-tokens.v2.json`
5. `design-pages/Gate 5.2C - Final Component Contract R3.1.dc.html`
6. `design-pages/gate5.2c-screen-data.v3.1.js`
7. Gate 5.2D Hi-Fi Waves 1–6 as visual references

## Scope: Gate 5.2D-A only

Implement the foundation, generated backend contracts, RTL token/primitives, application shell, T8 first-owner flow, and T9 returning-owner flow. Do not start the remaining T10–T18 flows in this slice.

### 1. Repository and contract checks

- Inspect the existing frontend stack; do not replace it or silently introduce a new framework.
- If there is no frontend repository or no approved stack, stop and return `STACK BLOCKED` with 2–3 compatible options and a recommendation. Do not scaffold by assumption.
- Locate the authoritative backend OpenAPI in the backend repository or export it from the backend.
- Verify its migration head/hash and compatibility with `BACKEND_CONTRACT_REQUIRED.md`.
- Generate API types/client bindings from OpenAPI. Do not manually duplicate DTOs.
- If the contract is missing or incompatible, stop integration work and return `CONTRACT BLOCKED` with exact differences.

### 2. Foundation

- Configure Persian RTL globally and use logical CSS properties.
- Implement the canonical tokens without runtime Google Fonts.
- Create the accessible primitives: Button, IconButton, Input, OTP input, Card, PetSwitcher, BottomNav/application shell, Sheet, Dialog, Toast, Banner, Skeleton, EmptyState, and ErrorState.
- Add policy gating from runtime `PolicyResponse`. Disabled capabilities render nothing customer-facing unless the contract defines a factual unavailable state.
- Create the generated API layer, authentication/session boundary, error mapping, query/cache conventions, and test fixtures derived from generated types.
- Never copy `design-pages/support.js` or the designer HTML runtime into production.

### 3. T8 — first owner

Implement the accepted vertical path:

OTP request/validation → optional pet onboarding → commerce remains usable if onboarding is skipped → incoming paid order state → delivery/inventory receipt → confirmed bag opening/setup → Today without premature consumption estimate.

The product may activate Today before the bag opens, but must show incoming/setup status rather than remaining-food days.

### 4. T9 — returning owner

Implement the accepted Today path:

active pet/switcher → most important current food/care status → next relevant event → compact Persian Garden preview.

Today must be understandable without a tap, must not require daily feeding logs, and must preserve household inventory versus pet-consumption boundaries.

### 5. Required invariants

- Persian RTL and Iran-first formatting.
- Store money as IRR; any toman display divides by 10 and explicitly labels تومان.
- Exact delivery commitment is 366 hours.
- Sourcing begins only after successful full payment.
- Reserve-now is modeled but disabled.
- Care journeys are enabled only from runtime policy and only for approved, active, eligible, professionally referenced definitions.
- No estimate starts before confirmed bag opening.
- No unapproved clinical logic or copy is embedded in the client.
- No purchase, visit, streak, decay, or health-score mechanics in Garden.
- Money, logistics, delays, and failures use literal language.

### 6. Verification

Add and run:

- generated-contract drift/check command;
- typecheck, lint, unit, and component tests;
- tests for policy fail-closed behavior;
- tests for OTP normal/error/lock states;
- tests proving no estimate before opening;
- tests for pet switching and household/pet separation;
- accessibility checks including keyboard/focus/labels and reduced motion;
- responsive checks at 320, 390, 768, and 1024px;
- production build.

Do not claim a check passed unless you ran it. If local dependencies or services prevent a check, state the exact command and blocker.

## Required result format

Return:

1. Outcome: implemented, `STACK BLOCKED`, or `CONTRACT BLOCKED`.
2. Repository/stack detected.
3. Files changed.
4. T8 and T9 behavior completed.
5. Backend operations and generated schemas used.
6. Policy/feature gates implemented.
7. Tests and builds run with exact results.
8. Remaining contract, asset, content, or policy blockers.
9. Recommended next implementation slice.

Do not expand scope, invent operational policy, or redesign the accepted system.
