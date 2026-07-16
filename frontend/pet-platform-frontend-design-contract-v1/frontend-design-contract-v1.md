# Pet Platform Frontend Design Contract v1

**Contract ID:** `PET-FE-DESIGN-v1`  
**Date:** 2026-07-16  
**Language/direction:** Persian (`fa-IR`), RTL-first  
**Status:** Approved implementation baseline; Gate 4 research validation is still pending P0 and the 6–8 participant study.  
**Applies to:** Design system, frontend component behavior, screen/state composition, customer-facing trust and uncertainty presentation, responsive behavior, motion and accessibility.

This contract consolidates the approved design record into one engineering source. It is framework-neutral. It does not define HTTP endpoints or replace the backend domain contract.

## 1. Normative source precedence

When two source documents disagree, use this order:

1. **This contract** — explicit consolidation and conflict resolution.
2. **Founder-approved product decisions** — domain rules and MVP boundaries. Later approved experience gates supersede the earlier universe metaphor only at the UX/IA layer.
3. **Gate 4 Research Prototype + `gate4-data.v1.js`, revision G4-R1** — exact behavior and customer copy for the critical research paths.
4. **Gate 3B Hi-Fi System + `gate3b-data.js`, revision 3B.1** — complete pet-life screen/state system, components, responsive rules and engineering annotations.
5. **Gate 3A Visual Calibration** — visual tokens, cornerstone compositions, motion, accessibility and pixel calibration.
6. **Gate 2.1 consistency corrections**.
7. **Gate 2 UX System, revision 2.1** — behavioral rationale and state-transition intent.
8. **Gate 2 clickable lo-fi prototype** — flow skeleton only.
9. **Earlier boards** — historical or provisional references only.

`support.js` is a design-document runtime dependency. It must not be copied into the production application.

## 2. Source classification

| Source | Contract use | Authority |
|---|---|---|
| `Gate 3A - Visual Calibration.dc.html` | Type, color, spacing, radii, elevation, cornerstone layouts, motion, reduced motion, RTL, touch and contrast | Normative |
| `Gate 3B - Hi-Fi System.dc.html` | Component APIs, responsive behavior, full flows A–G/S, edge states and engineering rules | Normative |
| `gate3b-data.js` | Full 3B screen/state content required to render the master hi-fi system | Normative except where G4-R1 overrides |
| `Gate 4 - Research Prototype.dc.html` | Latest clickable critical paths | Highest UI authority for covered paths |
| `gate4-data.v1.js` | Exact G4-R1 copy, branching and state examples | Highest UI authority for covered paths |
| `Gate 2 - UX System.dc.html` | Behavioral reasoning and hierarchy | Supporting |
| `Gate 2 - Prototype (Lo-fi).dc.html` | Navigation/flow skeleton | Supporting |
| `Gate 2.1 - Consistency Patch.dc.html` | Audit trail for corrected contradictions | Supporting |
| `uploads/pet_platform_product_decision_record.md` | Business/domain constraints | Normative, subject to later approved UX revision |
| `Hi-Fi Screens.dc.html` | Missing commerce surfaces only: shop, cart, checkout, concierge, wallet and pet profile | Provisional; not production-contract authority |
| `Design Direction Board.dc.html`, `Journey Caravan.dc.html`, `Universe Journey.dc.html`, Gate 1/1.1 | Historical concept evolution | Non-normative |
| `Gate 4 - Research Kit.dc.html` | Research operations | Not a UI specification |

## 3. Resolved conflicts and non-negotiable rules

1. **No universe/planet information architecture.** The pet-life system is the product architecture. Celestial/caravan language may remain atmospheric in order tracking or seasonal campaigns, never primary navigation.
2. **Pet is the experience noun; household is the ownership boundary.** Bags belong to household inventory. Consumption belongs to pets. A shared physical package is never duplicated per pet.
3. **No estimate before confirmed opening.** Delivery mutates inventory only. It cannot create a food estimate.
4. **Unknown is first-class.** `نمی‌دانم` produces a visibly wider, striped household-level band and withholds per-pet numbers when shares are unknown.
5. **Notification is not an order.** `به من خبر بده` must result in a notification subscription confirmation and explicitly create no order.
6. **Trust wording is constrained.** Use `اصالت: تأییدشده توسط تأمین‌کننده`. Show supplier country, keep supplier identity private, show dated reference-price saving, and show the minimum remaining shelf-life guarantee.
7. **No unsupported authenticity claim.** Never say `۱۰۰٪ اصل` or equivalent.
8. **Money and logistics are literal.** Dates, amounts, deadlines and states are never represented only through metaphor.
9. **Status is never color-only.** Every status uses glyph + Persian word; money/time states also show the literal amount/date.
10. **Garden is memory, not health.** No health score, XP, decay, punishment, purchase-to-progress or obligation.
11. **Care content is gated.** If content or clinical/escalation wording lacks professional approval, render no content—not `pending`, a disabled promise or an approval badge.
12. **External purchase is respected.** It can enter household inventory and continue the estimate lifecycle.
13. **Policy-pending UI stays disabled.** Delay compensation, cancellation after sourcing, sourcing failure, refunds and replacement promises are not customer-visible until a separate approved policy contract exists.
14. **Reserve-now is disabled for the initial release.** The domain may model it, but the production UI must not expose it until payment and approval policies are finalized.

## 4. Product shell and information architecture

### 4.1 Primary navigation

The mobile bottom navigation contains exactly five destinations in this order in RTL presentation:

| Navigation ID | Persian label | Responsibility |
|---|---|---|
| `today` | امروز | Active pet context, food state, next event, restrained Garden preview |
| `inventory` | انبار خانه | Household-owned open/unopened/external/unassigned product units |
| `diary` | دفترچه | Pet records, memories and journey history |
| `shop` | فروشگاه | Product discovery and commerce |
| `account` | حساب | Household identity, access, settings and future wallet entry |

The active destination uses primary ink, heavier weight and its icon. Navigation must remain literal; no planet labels.

### 4.2 Today composition

Fixed order:

1. active pet identity and `PetSwitcher`;
2. `FoodModule`;
3. at most one next event/action;
4. 76px `GardenStrip` preview;
5. bottom navigation.

An empty day is read-only and says that nothing is required. A module failure must not blank the page. Identity loads from cache first; remaining modules load independently at final geometry.

### 4.3 Surface modes

- Commerce, inventory, care, Today and order facts use warm light surfaces.
- Full Garden surfaces may use immersive dark green depth.
- Garden previews inside Today are compact and must not turn Today into an immersive destination.
- Exceptions break the atmospheric character and use plain factual sheets.

## 5. Design tokens

The machine-readable source is `frontend-design-tokens.v1.json`.

### 5.1 Typography

| Token | Family | Weight | Size | Line height | Use |
|---|---:|---:|---:|---:|---|
| `display` | Estedad | 800 | 27px | 1.5 | Primary Persian screen heading |
| `title` | Estedad | 700 | 17px | 1.6 | Section/page title |
| `body` | Vazirmatn | 400 | 13.5px | 1.9 | Default customer-facing text |
| `bodyStrong` | Vazirmatn | 700 | 13.5px | 1.8 | Emphasis/row value |
| `caption` | Vazirmatn | 400 | 11.5px | 1.7 | Supporting copy |
| `qualifier` | Vazirmatn | 600 | 10px | 1.5 | Provenance/estimate tags |
| `money` | Vazirmatn | 800 | 21px | 1.5 | Persian-digit monetary amount |
| `moneyUnit` | Vazirmatn | 500 | 12px | 1.5 | تومان label |
| `ltrData` | IBM Plex Mono | 400/500 | 10.5px | 1.5 | SKU/order code only, isolated LTR |

Rules:

- Customer-facing body text never drops below 13.5px; captions never below 11px.
- Persian line height is at least 1.5.
- Customer-facing digits are Persian.
- Use tabular numerals for money.
- Latin identifiers are wrapped in an isolated LTR context.
- Preserve Persian ZWNJ compounds.

### 5.2 Spacing and geometry

- Base unit: 4px.
- Allowed spacing scale: 4, 8, 12, 16, 20, 24, 32.
- Reference mobile screen padding: 20px.
- Narrow mobile padding: 16px.
- Card padding: 14–16px.
- Module gap: 12px.
- Section gap: 24px.
- Interactive target: minimum 44×44px.
- Minimum gap between interactive targets: 8px.
- `GardenStrip` height: exactly 76px.
- Field radius: 8px.
- Button radius: 10px.
- Card/module radius: 14px.
- Sheet radius: 20px on leading corners.
- Pill radius: 999px.

### 5.3 Elevation

- `e0`: 1px hairline border for resting cards.
- `e1`: `0 10px 30px oklch(0.3 0.02 265 / 0.08)` for phone/dialog/sheet elevation.
- Garden reveal glow only: `0 0 20px oklch(0.72 0.13 70 / 0.35)`.
- Glow is prohibited on commerce and money surfaces.

## 6. Component contract

### 6.1 Foundation components

#### `Button`

Variants: `primary | secondaryBrass | quiet | text | gardenGold | gardenQuiet`  
States: `default | pressed | focusVisible | disabled | loading`  
Minimum height: 44px.

- `primary` is reserved for payment and explicit confirmation.
- `secondaryBrass` is for care/progress actions, not prices.
- Decline/skip actions must be equal-sized and never shame-styled.
- Focus ring is 2px brass around the primary-ink pressed/focus state.

#### `StatusChip`

```ts
type StatusChipProps = {
  glyph: '●' | '◐' | '○' | '⚠' | '✓';
  labelFa: string;
  tone: 'positive' | 'info' | 'warning' | 'muted';
  dateFa?: string;
};
```

Color is never the sole state channel.

#### `SheetDecision`

Used only for assignment, opening, exception and other mid-flow decisions. Never use it for promotion. On landscape/keyboard view, maximum height is 70vh with internally scrolling content and pinned actions.

#### `Toast`

Factual, short and non-celebratory. Notification confirmation must explicitly state that no order was created.

### 6.2 Domain components

#### `PetSwitcher`

```ts
type PetSwitcherProps = {
  pets: PetSummary[];
  activeId: string;
  onSwitch: (petId: string) => void;
  onAdd?: () => void;
};
```

- 44px minimum chip height.
- Active state uses brass tint + heavier weight + border.
- At four or more pets, chips scroll horizontally and the active chip stays visible.
- At 320–359px, chips after the third pet may become text-only.

#### `FoodModule`

```ts
type FoodModuleState = 'incoming' | 'active' | 'unavailable' | 'error' | 'setup';
type FoodModuleProps = {
  state: FoodModuleState;
  product?: ProductSummary;
  order?: OrderSummary;
  estimate?: FoodEstimate;
  error?: ModuleError;
};
```

- Owns the second slot on Today.
- Must not render remaining-day estimates for `incoming` or `setup`.
- A local error boundary renders only the failed module state.

#### `MeterBand`

```ts
type MeterBandProps = {
  scope: 'pet' | 'household';
  minDays: number;
  maxDays: number;
  markerDays?: number;
  confidence: 'high' | 'mid' | 'unknown';
  provenance: ProvenanceRow[];
};
```

- `scope=household` with unknown shares requires a striped band.
- Unknown shares hide per-pet values.
- Never expose a raw confidence score.
- Confidence is communicated by word + band width + texture.

#### `QuarterScale`

Canonical options:

- `full` — پر
- `moreThanHalf` — بیش از نصف
- `lessThanHalf` — کمتر از نصف
- `nearEmpty` — ته کیسه

The same control is used during setup and correction.

#### `EventCard`

```ts
type EventCardProps = {
  source: 'owner' | 'journey' | 'system';
  titleFa: string;
  subtitleFa?: string;
  actionable: boolean;
  progress?: { current: number; total: number };
};
```

Today shows at most one actionable event. Journey events use `روز X از Y` only inside an active approved journey.

#### `GardenStrip`

Preview-only, exactly 76px tall. It may show pet presence, current object/memory and next eligibility reason. Tap opens `GardenStage`. It must never lead the Today hierarchy.

#### `GardenStage`

```ts
type GardenStageProps = {
  petId: string;
  quadrants: GardenQuadrant[];
  slots: GardenSlot[];
  objects: GardenObject[];
  nextEligibility?: GardenEligibility;
  reducedMotion: boolean;
};
```

- Each object references a durable `memoryId`.
- Placement supports drag and tap-to-place.
- Removal moves an object to storage; it is not destroyed.
- No client-side XP, health score or hidden progress counter.

#### `OrderTimeline`

```ts
type OrderTimelineProps = {
  orderId: string;
  events: Array<{ id: string; status: string; occurredAt: string; labelFa: string }>;
  promisedDeliveryAt?: string;
  revisedDeliveryAt?: string;
};
```

Only confirmed backend facts render. Atmosphere may frame the timeline but cannot replace dates/statuses.

## 7. Canonical frontend view models

These are UI contracts, not transport DTOs.

```ts
type PetSummary = {
  id: string;
  nameFa: string;
  species: 'cat' | 'dog';
  avatarUrl?: string;
};

type ProductSummary = {
  id: string;
  titleFa: string;
  imageUrl?: string;
  packageSizeLabelFa: string;
};

type ProductOffer = {
  product: ProductSummary;
  availability: 'ready' | 'reserved_disabled' | 'unavailable';
  platformPriceIrr?: number;
  referencePriceIrr?: number;
  savingPercent?: number;
  referencePriceReviewedAt?: string;
  trust: {
    supplierVerified: boolean;
    supplierCountryFa: string;
    supplierIdentityPublic: false;
  };
  minimumShelfLifeMonthsAtDelivery: number;
  promisedDeliveryDays: 14;
};

type OrderSummary = {
  id: string;
  state: 'payment_confirmed' | 'sourcing' | 'in_transit' | 'delayed' | 'delivered';
  promisedDeliveryAt: string;
  revisedDeliveryAt?: string;
  plannedPetIds: string[];
};

type InventoryItem = {
  id: string;
  householdId: string;
  product: ProductSummary;
  source: 'platform' | 'external';
  state: 'unopened' | 'open' | 'finished';
  openedAt?: string;
  consumerPetIds: string[];
  sharesKnown: boolean;
};

type FoodEstimate = {
  id: string;
  inventoryItemId: string;
  scope: 'pet' | 'household';
  petId?: string;
  minDays: number;
  maxDays: number;
  markerDays?: number;
  confidence: 'high' | 'mid' | 'unknown';
  provenance: ProvenanceRow[];
  lastConfirmedAt?: string;
};

type ProvenanceRow = {
  key: string;
  labelFa: string;
  valueFa: string;
  source: 'recorded' | 'owner_stated' | 'unknown';
};

type GardenObject = {
  id: string;
  objectType: string;
  memoryId: string;
  slotId?: string;
  stored: boolean;
};
```

## 8. Command intent contract

Frontend code emits domain intents; it does not infer policy.

| Intent | Required result |
|---|---|
| `purchaseOffer` | Paid order confirmation or factual gateway failure |
| `assignOrderPlan` | Optional planned pet assignment; no consumption mutation |
| `confirmInventoryOpening` | Opens inventory item; only event allowed to start an estimate |
| `setConsumptionKnowledge` | Known per-pet input or explicit unknown household scope |
| `correctRemainingAmount` | Applies quarter-scale correction and returns recalculated band |
| `registerExternalPurchase` | Creates household inventory with external source |
| `subscribeAvailability` | Creates notification subscription only; never an order |
| `snoozeReorder` | Suppresses in-app card and mirrored push for 72h unless pessimistic bound worsens |
| `acknowledgeDelay` | Records acknowledgement; does not imply compensation or cancellation |
| `placeGardenObject` | Stores object/slot relationship; object already has server-issued eligibility and memoryId |
| `stopJourney` | Respected completion state; no failure label |

## 9. Screen and state contract

The full machine-readable matrix is `frontend-screen-contract.v1.json`.

### Flow A — Commerce → activation

| ID | Screen | Required components/data | Commands |
|---|---|---|---|
| A1 | Product ready to order | ProductOffer, trust panel, reference price/date, shelf-life promise | `purchaseOffer` |
| A2 | Order placed | paid amount, order ID, promised date, optional assignment | `assignOrderPlan` |
| A3 | Minimal pet profile sheet | name + species only; skippable | create minimal profile / skip |
| A4 | Today incoming | PetSwitcher, incoming FoodModule, next event, GardenStrip | open order journey |

### Flow B — Today

| ID | State | Contract |
|---|---|---|
| B1 | Active | Food estimate plus one journey check-in |
| B2 | Empty day | Read-only; no manufactured task |
| B3 | Loading | Cached identity first; skeletons at final geometry |
| B4 | Module error | Local muted error; other modules remain usable |
| B5 | Return after absence | No guilt; wider band and one optional confirmation |

### Flow C — Food meter

| ID | State | Contract |
|---|---|---|
| C1 | Confirm opening sheet | Gate that starts estimate eligibility |
| C2 | Remaining + portion sheet | QuarterScale + known/unknown choice |
| C3 | Shared bag shares | Owner-stated or unknown; never automatic fake precision |
| C4 | Mixed feeding | Owner-stated dry share or unknown |
| C5 | Detail/correction | Band, confidence word, provenance, QuarterScale |
| C6 | External purchase | Same inventory and estimation lifecycle |

### Flow D — Reorder

| ID | State | Contract |
|---|---|---|
| D1 | Reorder card | Outcome first; max one card |
| D2 | How calculated | Disclosure on request only |
| D3 | Options | Each alternative states speed/availability reason only |
| D4 | Bought elsewhere | Add external bag; no platform sulking |
| D5 | Unavailable | Muted, notify/concierge, no auto-substitution |
| D6 | Snoozed | Quiet for 72h unless pessimistic bound worsens |

### Flow E — Care journey

Structure is design-ready; production content is approval-gated.

| ID | State | Contract |
|---|---|---|
| E1 | Offer | Never auto-started; appears only when eligible |
| E2 | Plan review | Neutral structure until professional content approval |
| E3 | In-window check-in | Exists only during active journey |
| E4 | Exception | No diagnosis; escalation copy gated |
| E5 | Paused/stopped | Respected outcome |
| E6 | Completion/memory/reveal | Preference saved only with explicit confirmation |
| E7 | Diary memory | Durable record linked to Garden object |

### Flow F — Persian Garden

| ID | State | Contract |
|---|---|---|
| F1 | First visit | Plot, faint quadrant plan, pet presence, exactly one next slot |
| F2 | Object reveal | One reveal per real milestone; total motion ≤1.2s |
| F3 | Placement | Drag + tap fallback; reversible to storage |
| F4 | Established | Object→memory link, visible X/Y rule, next reason |
| F5 | Memory detail | Emotional rendering of diary record |
| F6 | Inactivity return | Alive, no decay/recovery task |
| F7 | Quadrant full | Next quadrant opens by visible completed-slot rule; no XP |

### Flow G — Multi-pet/household

| ID | State | Contract |
|---|---|---|
| G1 | Today switched pet | Pet layer swaps; household inventory persists |
| G2 | Household inventory | Open/unopened/external/unassigned are valid |
| G3 | Unknown shares | Striped household band; per-pet values hidden |

### Flow S — Order journey

| ID | State | Contract |
|---|---|---|
| S1 | In transit | Timestamped confirmed events and promised date |
| S2 | Delayed | Old/new dates only; plain factual sheet |
| S3 | Delivered | Adds unopened inventory; no estimate |

## 10. Gate 4 G4-R1 overrides

For these research paths, copy and branching must match G4-R1 exactly until evidence-based Gate 4.1 revisions exist:

1. Product trust panel includes supplier-verified authenticity, Germany as sample supplier country with identity private, 36% saving relative to reference price, reference review date, 14-day commitment and six-month shelf-life guarantee.
2. Incoming Today shows no days-remaining number.
3. Delivered/opening diverges:
   - known daily share → per-pet estimate;
   - `نمی‌دانم` → wide striped household band and no per-pet number;
   - unopened → returns to incoming/unopened state.
4. Shared inventory explicitly says ownership is household and consumption is Pishi + Rex.
5. Availability notification confirmation says no order was created.
6. Delayed existing order is a separate scenario from notification and shows only original/revised dates.
7. Garden completion uses neutral care-path wording and lands back on a calm Today state.

Sample products, prices, dates, pet names and estimates are fixtures—not production constants.

## 11. Responsive contract

| Width | Behavior |
|---|---|
| 320–359px | 16px screen padding; 56px meter ring; after three pets chips may become text-only; body size remains 13.5px |
| 360–430px | Reference mobile composition; 20px padding |
| 431–599px | Content max-width 430px centered; Garden stage grows to available width |
| ≥600px | Today becomes two RTL columns; sheets become centered max-480px dialogs; Garden stage max 560px with object list beside it |
| Landscape/keyboard | Sheets ≤70vh; internal scroll; actions pinned |

Use CSS logical properties only. Do not create separate hand-mirrored layouts.

## 12. Motion contract

| Element | Default | Reduced motion |
|---|---|---|
| Garden presence | Ripple 8s, sway 12s, pet blink/tail; total displacement ≤2% | Static illustration and glow |
| Object reveal | 400ms glow + 500ms scale + 300ms settle; total ≤1.2s | ≤200ms crossfade |
| Placement | lift 150ms; snap 250ms; 24px forgiving radius; toast 2s | tap-only, instant snap |
| Meter correction | band/marker 300ms ease-out; number crossfade | final value + ≤120ms crossfade |
| Sheet | 260ms decelerate with scrim | opacity-only, 260ms |
| Toast | 180ms fade | same |
| Today module | 160ms per-module crossfade; zero layout shift | same |

No information is motion-gated. No decorative commerce animation, spring overshoot, confetti or sound by default.

## 13. Accessibility and localization acceptance

- Root customer surface uses `dir="rtl" lang="fa"`.
- Interactive targets are at least 44×44px and 8px apart.
- Row links include padded hit areas, not text-only targets.
- Garden objects have invisible 44px tap regions and a list fallback for dense areas.
- Keyboard focus is visible.
- Status meaning survives grayscale and color-vision differences.
- Contrast targets from the design source must be remeasured in the production build:
  - ink/surface ≈12.5:1;
  - secondary ink/surface ≈6.9:1;
  - white/primary ≈13:1;
  - brass-ink/surface ≈4.7:1;
  - Garden text/Garden deep ≈9:1.
- Raw brass is decorative-only on light surfaces; use brass-ink for text.
- `prefers-reduced-motion` behavior is mandatory.
- Money, dates and quantities are accessible text, never baked only into images.

## 14. Production feature flags

```ts
type FrontendPolicyFlags = {
  reserveNow: false;
  delayCompensation: false;
  cancelAfterSourcing: false;
  sourcingFailureSelfService: false;
  refundsSelfService: false;
  replacementSelfService: false;
  careJourneyContentApproved: boolean;
};
```

Disabled features render nothing unless a separately approved fallback is defined. Internal placeholders must never reach the customer DOM.

## 15. Legacy commerce coverage and gaps

The later Gate 3B/Gate 4 system does not provide production-complete designs for every commerce route. The following old `Hi-Fi Screens.dc.html` pages may be used only as provisional layout references:

- 02 Direct shop;
- 04 Product detail available (trust/copy overridden by G4-R1);
- 06 Unavailable (behavior overridden by G4-R1);
- 07 Comparison;
- 08 Cart;
- 09 Pet creation;
- 10 Checkout;
- 11 Confirmation;
- 15 Shelf life;
- 16 Concierge;
- 17 Replenishment;
- 18 Wallet;
- 19 Pet profile.

Do not implement legacy screens 01 Homepage two-door or 03 Universe entry. Do not use legacy tracking/delay screens 12–14 where Gate 3B/G4 exists. Screen 05 Reserve now is disabled for the initial release.

Before pixel-final implementation of the provisional routes, create a Gate 5 commerce completion patch that applies the current tokens, navigation, trust wording, policy flags and pet-life architecture.

## 16. Recommended implementation sequence

1. **Foundation:** fonts, direction provider, digit/date/money formatting, tokens, icons and accessibility primitives.
2. **Component library:** Button, StatusChip, PetSwitcher, FoodModule, MeterBand, QuarterScale, EventCard, GardenStrip, SheetDecision, OrderTimeline.
3. **G4 happy path:** product trust → paid order → incoming Today → delivery/opening → known/unknown estimates → correction → shared inventory.
4. **G4 exception path:** reorder reasoning → unavailable → notify/external purchase → separately delayed order.
5. **G4 Garden path:** neutral completion → memory → placement → calm Today.
6. **Full 3B states:** loading/error/absence, full meter, Garden, multi-pet and order variants.
7. **Gate 5 commerce completion:** shop, compare, cart, checkout, concierge, account/wallet and progressive pet profile.

The design system and G4 paths can be coded before research completes. Gate 4.1 findings may change copy or interaction details, so keep screen content and transitions configuration-driven.

## 17. Definition of frontend design compliance

A screen is contract-compliant only when:

1. it uses normalized tokens rather than copied inline prototype styles;
2. it implements the specified component variants and data states;
3. loading, empty, error and unknown states are present;
4. RTL, Persian digits, ZWNJ and LTR isolation are correct;
5. mobile and tablet breakpoints follow this contract;
6. no disabled policy or internal placeholder reaches the customer;
7. critical G4-R1 branching and copy are preserved;
8. accessibility and reduced-motion checks pass;
9. business values come from backend/configuration, not design fixtures;
10. any deviation is recorded as a versioned contract amendment.

## 18. Explicit non-goals

This contract does not:

- select React, Next.js or another frontend framework;
- define API URLs, authentication mechanisms or server DTOs;
- approve old universe navigation;
- approve care/medical wording;
- approve policy-pending cancellation/refund/replacement/compensation UI;
- turn sample Persian text, product names, prices, dates or calculations into production constants;
- claim that Gate 4 user validation is complete.

