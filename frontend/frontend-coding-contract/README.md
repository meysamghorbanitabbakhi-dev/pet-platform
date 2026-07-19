# Pet Platform frontend coding contract — Gate 5.2D-A

Status: **accepted implementation baseline**, corrected as R3.1 on 2026-07-17.

This package is the canonical handoff for frontend implementation. It accepts the designer's Gate 5.2C R3 system and Gate 5.2D Waves 1–6 while correcting three handoff defects: the stale disabled care-journey declaration, missing `/api/v1` prefixes, and the incomplete journey component contract.

## Authority order

When sources disagree, use this order:

1. Runtime API responses and runtime policy flags.
2. The current backend repository's generated OpenAPI document.
3. `BACKEND_CONTRACT_REQUIRED.md` and the accepted product rules below.
4. `design-pages/gate5.2c-screen-data.v3.1.js` for screen graph and presentation intent.
5. Hi-fi boards and prototypes for visual composition.

Design fixtures never override the backend. Never invent missing API fields or operational policy.

## Canonical file integrity

Every file under `design-pages/` is checksum-governed by `canonical-manifest.sha256` (`sha256sum -c canonical-manifest.sha256`, also run as part of `pnpm check:contract`). These files are frozen point-in-time snapshots — including any migration head, path/operation counts, or hash they mention in their own text. **Never edit a canonical `.dc.html` file to add a "current authority" banner or any other live annotation; that both falsifies the checksum and makes the file lie about being unmodified.** If a canonical file needs a historical/no-longer-current-authority notice, add it here or in `ACCEPTED_PAGE_REGISTER.md` instead — never inside the file itself. The only current-release authority is `backend/release-contract.json`; nothing in `design-pages/` is ever a source of current release facts, however it reads.

## Accepted product model

- Persian RTL, mobile-first, Iran-first hybrid architecture.
- Commerce is available without a pet profile.
- Household owns physical inventory; pets receive consumption assignments.
- Today is the calm read-mostly hub: pet identity, current need/food, next event, compact Garden.
- Food estimates begin only after delivery, inventory receipt, confirmed opening, and setup. Estimates are ranges with confidence and correction.
- Orders are sourced only after full payment. Reserve-now is modeled but disabled until payment and approval policies are finalized.
- Money is stored in IRR. UI may display toman by dividing by 10 and must label the unit.
- The delivery commitment is exactly 366 hours. Do not resurrect 336-hour or generic 14-day copy.
- Care journeys are enabled only when the runtime flag is true and content is approved, active, species-eligible, and professionally referenced.
- Diary is the durable record. Persian Garden is an optional emotional rendering of legitimate milestones, never a health score, purchase reward, streak, or penalty.
- Order status, money, failures, delays, and support are literal and non-metaphorical.
- A single 360-degree operator role administers the platform in the initial release.
- Pet owners may upload medical documents and pet body photographs through backend-governed media flows.

## Disabled until policy closure

Reserve payment, self-service refund/replacement/substitution, cancellation after sourcing, delay-compensation visibility, late-credit visibility, and push notifications must remain absent or fail closed unless runtime policy explicitly enables them.

## Package map

- `NEXT_AGENT_PROMPT.md`: first implementation slice and acceptance criteria.
- `BACKEND_CONTRACT_REQUIRED.md`: mandatory OpenAPI check and blocker behavior.
- `ACCEPTED_PAGE_REGISTER.md`: accepted design pages and implementation interpretation.
- `design-pages/`: final visual references, canonical data, component contract, tokens, and asset inventory.
- `design-pages/support.js`: **preview runtime only**. It exists solely so `.dc.html` boards render. Never copy it into production.

## Coding sequence

Gate 5.2D-A is foundation only:

1. Inspect the existing frontend repository and preserve its approved stack.
2. Generate client types from the actual backend OpenAPI.
3. Implement RTL foundations, tokens, primitives, application shell, and policy gating.
4. Implement T8 first-owner and T9 returning-owner vertical slices.
5. Add contract, unit, component, accessibility, and responsive tests.

Do not implement all 152 states in the first slice. Subsequent waves expand the accepted system after the foundation passes.

## Visual and accessibility invariants

- Estedad for display where licensed/bundled, Vazirmatn for body, IBM Plex Mono for identifiers; no runtime Google Fonts dependency.
- Midnight is decisive action; brass is restrained progress/selection/Garden accent.
- Minimum interactive target: 44px.
- Validate at 320, 390, 768, and 1024px.
- Status must not depend on color alone.
- Support keyboard navigation, visible focus, semantic labels, and reduced motion.
- Replace any remaining emoji or placeholder artwork with the approved asset family when assets are supplied; report `ASSET BLOCKED` rather than inventing final art.

## Definition of complete for this handoff

The design package is accepted as the implementation baseline. This does not mean the frontend is implemented, usability-tested in code, integrated with production providers, or release-ready. Those are engineering and validation gates.
