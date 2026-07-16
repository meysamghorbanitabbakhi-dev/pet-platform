# Pet Platform — Product Decision Record

**Document status:** Baseline decision record  
**Decision authority:** Founder-approved  
**Current phase:** MVP definition  
**Last updated:** 2026-07-13  
**Scope:** Consumer commerce entry point, demand-based sourcing, immersive shopping experience, household and pet-profile foundation, and future two-sided platform direction

---

## 1. Purpose of This Document

This document records the product, commercial, operational, trust, and experience decisions made for the pet platform.

It is intended to serve as the current source of truth for:

- product strategy;
- experience and design decisions;
- commerce and fulfillment logic;
- customer policies;
- data modeling;
- agent implementation prompts;
- acceptance criteria;
- future architecture decisions.

A decision remains locked unless it is explicitly reopened and replaced in a later decision record.

---

## 2. Executive Product Definition

The product begins as a **premium pet-nutrition commerce experience**, but the shop is not the final business.

The shop is the initial acquisition, trust, transaction, and data wedge for a broader two-sided platform organized around pets.

The long-term platform promise is:

> **Manage each pet's products, services, care journey, and history in one place.**

The launch promise is deliberately narrower:

> **Discover and buy trusted pet nutrition.**

The first commercial model uses demand-based sourcing and import. Customers accept a longer delivery period in exchange for transparent and potentially substantial savings compared with the Iranian market.

The immersive solar-system experience is not merely a visual theme. It is the interaction and progression layer through which customers discover products, complete purchases, follow orders, build pet profiles, and eventually access other areas of the pet ecosystem.

---

## 3. Core Strategic Thesis

### 3.1 The shop is the wedge

The nutrition shop creates repeatable value and gives the platform an initial reason to exist.

It can acquire:

- verified pet-owning households;
- recurring transactions;
- pet-specific demand data;
- nutrition preferences;
- consumption patterns;
- reorder timing;
- product and price sensitivity;
- trust around sourcing and pet care.

### 3.2 The pet profile is the durable asset

Products, services, providers, purchases, recommendations, records, missions, rewards, and future care interactions should connect to a persistent pet profile.

The catalog is not the permanent center of the platform. The pet is.

### 3.3 The future network is curated before it becomes open

The platform begins as an operator-controlled experience.

It may later include verified:

- product partners;
- veterinarians;
- groomers;
- trainers;
- boarding providers;
- walkers;
- pet-care professionals;
- other approved ecosystem participants.

The platform should not begin as an uncontrolled open marketplace.

---

## 4. Locked Product Principles

1. **Trust before scale.**
2. **The pet profile is the primary experience and intelligence entity.**
3. **The household is the ownership, access, payment, and transaction boundary.**
4. **The nutrition shop is the launch product, not the final platform.**
5. **The universe should improve discovery and retention, not make commerce harder.**
6. **Transactions must remain explicit even when the experience is imaginative.**
7. **Demand-based sourcing must be transparent.**
8. **Price advantage must be evidence-based at product level.**
9. **Paid customer commitments take priority over batch economics.**
10. **Uncertain products must not be presented as confirmed inventory.**
11. **Pet-profile data should be collected progressively and only when it creates visible value.**
12. **Normal progress may be immersive; exceptions and required actions must be clear.**
13. **No automatic payment or purchase should occur without customer approval.**
14. **The MVP should preserve future platform extensibility without implementing premature marketplace complexity.**

---

# Part I — Platform Strategy

## 5. Decision 0.1 — The Two Sides of the Platform

### Locked decision

> **Pet owners and a platform-curated pet ecosystem initially, evolving into a verified provider network.**

### Meaning

The demand side consists of pet-owning households.

The supply side begins as a platform-curated ecosystem rather than an open marketplace.

### Consequences

- The platform controls initial quality and experience.
- Provider onboarding is deferred.
- Verification and curation are mandatory before ecosystem participation.
- The architecture may remain extensible for future partners without exposing marketplace functions in the MVP.
- The customer experiences one coherent platform brand.

---

## 6. Decision 0.2 — Initial Seller and Fulfillment Model

### Locked decision

> **The platform initially owns and fulfills the core nutrition assortment. Selected verified partners may be introduced later under platform-controlled standards.**

### Consequences

The MVP does not require:

- seller onboarding;
- seller dashboards;
- commissions;
- marketplace settlements;
- split orders;
- multi-vendor returns;
- vendor-level customer support.

The platform remains directly accountable for:

- offer presentation;
- sourcing;
- price;
- customer payment;
- order status;
- delivery commitment;
- compensation;
- refunds;
- support.

---

## 7. Decision 0.3 — Central Entity Model

### Locked decision

> **A household account is the ownership and transaction boundary, while each pet profile is the primary experience and intelligence entity.**

### Household responsibilities

The household owns:

- user access;
- payment identity;
- addresses;
- wallet;
- orders;
- permissions;
- shared products;
- family access in future releases.

### Pet-profile responsibilities

Each pet profile owns or receives:

- identity;
- species;
- optional attributes;
- nutrition relationships;
- product assignments;
- consumption estimates;
- recommendations;
- missions;
- future services;
- future care history.

---

## 8. Decision 0.4 — Long-Term Core Promise

### Locked decision

> **Manage each pet's products, services, care journey, and history in one place.**

### Product implication

Every major future capability should strengthen a unified pet-centered journey.

A new feature or vertical should not be added merely because it is related to pets. It should improve coordination, continuity, trust, convenience, or intelligence around the pet.

---

## 9. Decision 0.5 — Launch Promise

### Locked decision

> **Discover and buy trusted pet nutrition.**

### Meaning

The launch message should lead with:

- nutrition;
- discovery;
- trust;
- access;
- value.

The broader platform vision should support the launch experience without overwhelming the initial proposition.

---

## 10. Decision 0.6 — Initial Target Customer

### Locked decision

> **Urban dog and cat owners in Iran who buy premium or trusted nutrition online.**

### Consequences

The initial experience should optimize for:

- mobile use;
- Persian RTL;
- premium but adult visual design;
- clear product information;
- trusted sourcing;
- price comparison;
- planned purchasing;
- multi-pet households;
- repeat nutrition needs.

The platform is not initially optimized for all pet owners or every price segment.

---

# Part II — Experience Boundaries

## 11. Product Experience Model

The founder accepted the recommended experience defaults for the remaining questions.

### Locked baseline

> **A premium pet-nutrition store with an optional interactive universe for guided discovery, education, basket building, progression, and rewards.**

### Rules

- The universe is optional.
- Direct shopping remains available.
- The experience may be cinematic and interactive.
- It should still be recognizably ecommerce.
- The universe should primarily improve product discovery.
- Entertainment is a presentation layer, not the main commercial objective.
- A journey should solve a pet need and help build a suitable basket.
- Space terminology must not reduce commercial clarity.
- Search, categories, product details, cart, account, and checkout must remain reachable.
- Checkout should be calm, conventional, and trustworthy.
- Primary commercial performance is completed conversion, followed over time by repeat purchase.

### Recommended entry behavior

Initial visitors should be able to choose between:

- **Shop directly**
- **Explore the universe**

Returning-user routing may later adapt to behavior and preference.

---

## 12. Canonical Universe Metaphor

The following terms are the current conceptual model. Final brand names remain open.

| Experience term | Business meaning |
|---|---|
| Universe | The complete pet platform |
| Solar system | A major pet-life domain or platform vertical |
| Planet | A need, category, destination, or service area |
| Moon | A subcategory, bundle, or supporting offer |
| Mission | A guided customer objective with a useful outcome |
| Cargo | Products associated with the current journey or order |
| Cargo hold | Cart |
| Journey | Discovery, purchase, delivery, or care progression |
| Warp transition | A major transition between platform areas |
| Household | Ownership, access, payment, and shared-supply boundary |
| Pet profile | Primary experience and intelligence identity |
| Wallet | Household-owned platform credit and benefits |

These metaphors are conceptual. Final customer labels must be tested for clarity and may require plain-language support.

---

# Part III — Commerce and Pricing

## 13. Decision 0.7 — Product-Level Price Advantage

### Locked decision

> **Each product displays a defensible market reference price and the exact customer saving. Savings vary by product and may reach approximately 50%.**

### Required offer data

Each eligible offer should contain:

- platform price;
- reference market price;
- absolute saving;
- percentage saving;
- reference-price verification date;
- delivery commitment;
- purchase state.

### Rules

- Do not promise a universal 50% discount.
- Do not inflate reference prices.
- “Up to 50% savings” may be used only while supported by current offers.
- Reference prices should be auditable internally.
- Pricing must be revalidated when exchange rates, supplier costs, or market prices materially change.

---

## 14. Decision 0.8 — Hybrid Payment Timing

### Locked decision

> **Confirmed-source products with locked landed cost require full payment. Products with uncertain availability or volatile landed cost use a reservation or deposit until sourcing is confirmed.**

### Product purchase states

#### Available to order

- reliable source;
- confirmed availability;
- locked customer price;
- full payment allowed.

#### Reserve now

- availability, landed cost, or source certainty is incomplete;
- reservation or deposit may be used;
- final sourcing requires later customer approval.

#### Temporarily unavailable

- no reliable sourcing path;
- no payable order should be accepted.

---

## 15. Decision 0.9 — Sourcing Failure and Price Changes

### Locked decision

> **Fully paid confirmed-source orders are price-protected. Reserved orders proceed only after the customer approves final availability, price, and delivery estimate. If sourcing fails, the customer may choose a full refund or an explicitly approved alternative.**

### Rules

- No automatic product substitution.
- A fully paid confirmed offer creates a firm platform obligation.
- Reserved offers remain conditional.
- Customer approvals must be recorded.
- Alternatives require explicit acceptance.
- Sourcing failure must not be disguised as a delivery delay.

---

# Part IV — Supply and Purchasing Cycles

## 16. Decision 0.10 — Hybrid Supply Model

### Locked decision

> **Predictable, high-confidence products are aggregated into purchasing cycles, while exceptional or high-value products may be sourced individually.**

### Aggregated route

Best suited for:

- repeat-demand products;
- reliable source availability;
- consolidated shipping;
- better landed economics.

### Individual route

Best suited for:

- rare products;
- high-value products;
- concierge requests;
- low-volume specialist demand.

The customer-facing order experience may remain unified even when operational routes differ.

---

## 17. Decision 0.11 — Hybrid Purchasing-Cycle Trigger

### Locked decision

> **Each grouped-import offer has a visible fixed weekly deadline, but sourcing may begin earlier once the batch reaches its minimum viable threshold.**

### Rules

- Every grouped offer has a published order deadline.
- Early sourcing is allowed when internal viability is reached.
- Batch progress may be used as engagement information.
- Paid fulfillment must not remain dependent on other customers after the deadline.

---

## 18. Decision 0.12 — Missed Batch Threshold

### Locked decision

> **The platform proceeds even when the minimum viable threshold is missed and absorbs the weaker unit economics.**

### Consequences

- A paid customer is not delayed because demand was lower than expected.
- Batch thresholds are internal financial controls.
- The platform requires a loss ceiling and exception process.
- Repeatedly uneconomic items should be repriced, moved to individual sourcing, or removed.
- Batch-progress messaging must not imply that customer delivery is conditional.

---

## 19. Decision 0.13 — Customer Cancellation

### Locked decision

> **Customers may cancel freely before sourcing begins. Once sourcing begins, cancellation is restricted unless the platform fails to meet the agreed terms.**

### Required implementation rule

“Sourcing started” must be:

- precisely defined;
- timestamped;
- auditable;
- visible in the internal order record;
- triggered by a real operational event.

It must not be used artificially to block cancellation.

---

# Part V — Delivery Commitment and Compensation

## 20. Decision 0.14 — Firm Delivery Commitment

### Locked decision

> **The order must reach the customer within 14 days.**

This is a firm end-to-end service commitment, not a soft estimate.

### Catalog consequence

A product should not be offered under the standard promise when the platform cannot reasonably support the commitment.

---

## 21. Decision 0.15 — Delivery Clock Start

### Locked decision

> **The 14-day clock starts when the customer successfully completes payment.**

### Consequences

- Batch waiting time counts against the commitment.
- The payment timestamp is the authoritative SLA start.
- Product availability and cycle cutoffs must account for remaining fulfillment time.
- The system should calculate and store the commitment deadline immediately after payment.

---

## 22. Decision 0.16 — Missed Delivery Commitment

### Locked decision

> **If delivery exceeds 14 days, fulfillment continues and the customer receives predefined compensation. A full refund is reserved for cases where the product cannot ultimately be delivered, subject to applicable customer-protection requirements.**

### Rules

- Late delivery does not automatically cancel the order.
- Delay status must be visible.
- Compensation must be automatic.
- Failed delivery and late delivery are different states.
- Repeated lateness should affect product and supplier eligibility.

---

## 23. Decision 0.17 — Compensation Basis

### Locked decision

> **Late-delivery compensation is calculated as a percentage of the delayed order's merchandise value.**

Shipping fees and payment fees are excluded from the compensation base.

---

## 24. Decision 0.18 — Compensation Rate

### Locked decision

> **The compensation rate is 5% of merchandise value.**

### Trigger

The compensation is created when the order crosses into day 15 without completed delivery.

---

## 25. Decision 0.19 — Compensation Instrument

### Locked decision

> **The 5% compensation is issued as platform wallet credit.**

### Wallet rules

- household-owned;
- not cash-withdrawable;
- visible in the account;
- usable on future purchases;
- recorded in an immutable wallet ledger.

---

## 26. Decision 0.20 — Compensation Expiry

### Locked decision

> **Late-delivery wallet credit expires three months after issuance.**

### Required behaviors

- display expiry date;
- remind the customer before expiry;
- retain expired credit in ledger history;
- define credit-consumption priority;
- disclose the rule before payment.

---

# Part VI — Communicating the Wait

## 27. Decision 0.21 — Combined Value Story

### Locked decision

> **The platform explains that efficient sourcing and demand aggregation produce better pricing, while the customer receives transparent progress throughout the 7–14 day journey.**

### Intended framing

The delivery period is a deliberate exchange:

- customer waits longer;
- platform sources efficiently;
- platform may consolidate demand;
- customer receives a material price advantage.

The experience must not misrepresent a constraint as instant availability.

---

# Part VII — Immersive Tracking

## 28. Decision 0.22 — Customer-Facing Tracking Model

### Locked decision

> **Order tracking is primarily immersive and represented through the universe narrative, planets, spacecraft, and journey events rather than a detailed operational timeline.**

### Internal requirement

The platform must still maintain precise real-world statuses internally.

### Integrity rule

A narrative state must never imply that an operational milestone has occurred when it has not.

---

## 29. Decision 0.23 — Exception Communication

### Locked decision

> **Normal progress remains narrative-only. Plain-language explanations appear when there is a delay, payment issue, sourcing problem, or required customer action.**

### Meaning

Immersion is permitted during normal progress.

Clarity is mandatory when:

- the customer must act;
- the commitment is at risk;
- money is affected;
- sourcing changes;
- delivery is delayed;
- an order cannot proceed.

---

# Part VIII — Checkout and Membership Activation

## 30. Decision 0.24 — What Checkout Unlocks

### Locked decision

> **Checkout transitions the customer from visitor to platform member and unlocks the household account, pet profiles, wallet, immersive order journey, missions, and future ecosystem areas.**

### Product implication

Checkout is not only order confirmation. It is the initial platform activation event.

Post-checkout onboarding should:

- be lightweight;
- connect directly to the purchase;
- explain immediate value;
- avoid unnecessary forms;
- introduce the pet-centered experience.

---

# Part IX — Pet Profiles

## 31. Decision 0.25 — Progressive Pet-Profile Creation

### Locked decision

> **A minimal pet profile is created or selected around checkout, then enriched over time through useful missions, recommendations, purchases, and future provider interactions.**

### Rules

- Browsing remains open.
- Full profile completion is not required before shopping.
- Profile enrichment should be contextual.
- Each additional field should unlock visible value.

---

## 32. Decision 0.26 — Adaptive Minimum Profile

### Locked decision

> **Always capture pet name and species. Request additional information only when it immediately improves the selected product, mission, recommendation, feeding guidance, or service interaction.**

### Potential progressive fields

- life stage;
- approximate age;
- birth date;
- breed;
- size;
- weight;
- sex;
- sterilization status;
- activity level;
- sensitivities;
- nutritional goals.

Unknown data must remain unknown. The platform should not infer sensitive care information without support.

---

# Part X — Product Allocation and Household Supply

## 33. Decision 0.27 — Hybrid Product-to-Pet Allocation

### Locked decision

> **Each cart item may be assigned to one pet, multiple pets, or shared household supply. Exact quantity allocation is optional at checkout and may be refined later.**

### Supported scenarios

- one product for one pet;
- one product shared by multiple pets;
- household stock not yet assigned;
- multiple units split later.

### Data rule

A shared package is one household inventory object. It must not be duplicated as separate physical inventory for every linked pet.

---

## 34. Decision 0.28 — Progressive Shared-Consumption Estimation

### Locked decision

> **The platform estimates shared consumption using known pet data, feeding guidance, package size, and assigned pets. The estimate is labeled clearly and improves through customer corrections and repeat-purchase behavior.**

### Inputs

Potential estimation inputs include:

- number of assigned pets;
- species;
- life stage;
- weight;
- feeding guidance;
- package weight;
- purchase date;
- prior reorder interval;
- customer corrections.

### Safety rule

Consumption estimates are planning aids, not medical advice.

---

# Part XI — Replenishment

## 35. Decision 0.29 — Automatic Reservation, Manual Approval

### Locked decision

> **When food is predicted to run low, the platform reserves the likely replenishment in the next purchasing cycle. The customer must review and approve before payment.**

### Rules

- reservation is not a paid order;
- no payment occurs automatically;
- no sourcing begins until approval;
- the customer reviews product, quantity, price, and pet assignment;
- active orders and household supply must be checked first.

---

## 36. Decision 0.30 — Reservation Timing

### Locked decision

> **The replenishment reservation is created 14 days before predicted depletion.**

### Consequence

There is no additional safety buffer beyond the maximum delivery commitment.

The platform should therefore monitor:

- prediction accuracy;
- approval delay;
- late deliveries;
- household stockouts;
- customer correction behavior.

---

## 37. Decision 0.31 — Approval Window

### Locked decision

> **The customer has 48 hours to approve the replenishment reservation.**

After 48 hours:

- the reservation expires;
- no sourcing slot is held;
- no payment is made;
- the state remains in history.

---

## 38. Decision 0.32 — Expired Reservation Behavior

### Locked decision

> **When the reservation expires, the platform sends one final reorder reminder and then stops.**

### Rules

- no repeated reservation loop;
- no automatic recreation for the same predicted cycle;
- no ongoing reminder pressure;
- the customer may still reorder manually;
- ignored reservations may improve future prediction logic.

---

# Part XII — Concierge Sourcing

## 39. Decision 0.33 — Unlisted Product Requests

### Locked decision

> **Customers may request a nutrition product that is not listed. The platform verifies authenticity, availability, landed price, and ability to meet the delivery commitment before presenting a payable offer.**

### Request states

Recommended states:

1. Submitted
2. Under review
3. Source under verification
4. Source verified
5. Offer ready
6. Unavailable
7. Expired
8. Accepted
9. Sourcing started
10. Completed

No payment should be taken before the offer is verified and presented.

---

## 40. Decision 0.34 — Hybrid Concierge Pricing

### Locked decision

> **When a reliable market reference exists, show the platform price and exact customer saving. When no reliable reference exists, show transparent landed cost plus the platform's sourcing margin.**

### Internal cost model

The platform should separately track:

- supplier cost;
- exchange-rate basis;
- international transport;
- customs or clearance exposure;
- handling;
- domestic delivery;
- payment fees;
- risk reserve;
- platform margin.

The customer-facing presentation should remain understandable rather than operationally dense.

---

## 41. Decision 0.35 — Dynamic Offer Validity

### Locked decision

> **Concierge offers remain valid for 12–48 hours depending on source reliability, supplier certainty, and price volatility, with 24 hours as the default.**

### Rules

- exact expiry timestamp;
- price locked during validity;
- expired offer cannot be paid;
- re-verification required after expiry.

---

## 42. Decision 0.36 — Recheck After Expiry

### Locked decision

> **An expired concierge request remains available, but the platform does not recheck automatically. The customer may request a refreshed offer.**

### Consequences

- no repeated sourcing work without intent;
- prior offer remains visible;
- refreshed price may differ;
- refreshed availability may differ;
- old offer is never silently reactivated.

---

## 43. Decision 0.37 — Concierge Product Promotion

### Locked decision

> **A concierge-sourced product may enter the public catalog only at platform discretion after validating recurring demand, reliable sourcing, acceptable economics, compliance, and consistent delivery performance.**

### Promotion criteria

- request frequency;
- conversion;
- repeat demand;
- source stability;
- authenticity confidence;
- landed margin;
- delivery performance;
- product documentation;
- customer feedback;
- operational complexity.

---

# Part XIII — Trust and Source Disclosure

## 44. Decision 0.38 — Initial Trust Standard

### Locked decision

> **A product initially qualifies as trusted based on supplier assurance.**

### Important risk statement

This is intentionally lightweight and creates elevated risk in:

- authenticity;
- product quality;
- customer claims;
- supplier dependency;
- legal liability;
- brand reputation.

This decision should be revisited before scale, broader supplier onboarding, or stronger authenticity claims.

---

## 45. Decision 0.39 — Customer-Facing Trust Label

### Locked decision

> **Use “Supplier-verified.”**

### Prohibited implication

The platform should not claim:

- 100% authentic;
- independently authenticated;
- batch verified;
- laboratory tested;

unless a stronger evidence standard is actually implemented.

### Required explanation

The product page should define “Supplier-verified” in plain language.

---

## 46. Decision 0.40 — Supplier Disclosure

### Locked decision

> **Show the supplier country and Supplier-verified status while keeping the supplier's identity private.**

### Required distinctions

The interface should not conflate:

- manufacturing country;
- brand country;
- supplier country;
- shipping origin;
- verification status.

The exact supplier identity and sourcing record should remain available internally.

---

# Part XIV — Expiry and Shelf Life

## 47. Decision 0.41 — Hybrid Expiry Transparency

### Locked decision

> **Before payment, show a minimum remaining shelf-life guarantee. After sourcing confirmation, share the exact expiry date.**

### Rules

- shelf-life promise must be visible before payment;
- exact expiry should be linked to the sourced unit or batch;
- a product below the promised minimum cannot silently proceed;
- customer acceptance of an exception must be explicit and recorded.

---

## 48. Decision 0.42 — Default Minimum Shelf Life

### Locked decision

> **The default minimum remaining shelf life is six months at delivery.**

### Rules

- six months is the standard acceptance threshold;
- a product-specific exception must be explicit;
- exact expiry remains visible after sourcing;
- future pack-size and consumption-fit rules may become more specific.

---

## 49. Decision 0.43 — Below-Threshold Shelf Life

### Locked decision

> **A sourced product with less than six months remaining may only be offered with explicit customer approval, exact expiry disclosure, and an additional discount.**

### Required customer information

The exception offer should show:

- exact expiry date;
- remaining shelf life at expected delivery;
- revised price;
- additional discount;
- reason the offer is exceptional;
- clear accept or reject actions.

The product must not be substituted into the order automatically.

---

# Part XV — Consolidated State Models

## 50. Product Purchase State

Recommended canonical states:

| State | Meaning |
|---|---|
| Available to order | Source and landed price are confirmed |
| Reserve now | Availability or landed cost requires confirmation |
| Temporarily unavailable | No reliable sourcing path |
| Concierge only | Available only through manual request |
| Shelf-life exception | Requires explicit expiry acceptance |

---

## 51. Order State

Recommended canonical business states:

1. Payment pending
2. Paid
3. Cancellation available
4. Sourcing started
5. Journey in progress
6. Domestic delivery
7. Delivered
8. Late — compensation issued
9. Sourcing failed
10. Refunded
11. Cancelled

The customer-facing journey may use narrative states, but the internal business state must remain exact.

---

## 52. Replenishment State

1. Prediction created
2. Reservation prepared
3. Customer notified
4. Approved
5. Expired
6. Final reminder sent
7. Converted to order
8. Dismissed

---

## 53. Concierge Request State

1. Submitted
2. Under review
3. Verification in progress
4. Offer ready
5. Offer expired
6. Refresh requested
7. Unavailable
8. Accepted
9. Converted to order
10. Closed

---

# Part XVI — Wallet Logic

## 54. Wallet Ownership

The wallet belongs to the household.

### Initial wallet use

The first locked wallet use case is late-delivery compensation.

### Required ledger fields

- transaction ID;
- household ID;
- source order;
- reason;
- credit amount;
- issuance timestamp;
- expiry timestamp;
- consumed amount;
- consumption order;
- status;
- audit metadata.

Wallet balance should be derived from ledger entries rather than stored as an untraceable mutable number.

---

# Part XVII — Data Model Direction

## 55. Core Entities

### Household

- account identity;
- members;
- addresses;
- payment relationships;
- wallet;
- orders;
- shared inventory.

### PetProfile

- household relationship;
- name;
- species;
- progressively collected attributes;
- assigned products;
- missions;
- estimated consumption;
- future service and care history.

### Product

- brand and product identity;
- nutrition attributes;
- manufacturer and origin;
- supplier-verification state;
- market-reference price;
- sourcing route;
- shelf-life rule.

### ProductOffer

- current platform price;
- saving;
- purchase state;
- source certainty;
- validity;
- delivery commitment;
- batch-cycle relationship.

### HouseholdInventoryItem

- purchased package;
- remaining estimated quantity;
- linked pets;
- shared-supply state;
- consumption estimate;
- predicted depletion.

### PurchaseBatch

- deadline;
- threshold;
- early-start state;
- included orders;
- sourcing start;
- economics.

### ConciergeRequest

- requested product;
- verification;
- offer;
- validity;
- customer decisions.

### WalletLedgerEntry

- immutable credit and debit history.

---

# Part XVIII — UX Requirements Derived From Decisions

## 56. Homepage

Must clearly support:

- direct shopping;
- universe exploration;
- trusted nutrition proposition;
- savings explanation;
- 7–14 day delivery commitment;
- supplier-verification explanation.

## 57. Product Page

Must show, where applicable:

- platform price;
- reference price;
- exact saving;
- Supplier-verified status;
- supplier country;
- manufacturing country;
- purchase state;
- weekly deadline;
- delivery commitment;
- minimum six-month shelf-life guarantee;
- product-to-pet relevance;
- checkout eligibility.

## 58. Checkout

Must remain commercially explicit.

It should show:

- product and quantity;
- pet or household-supply assignment;
- payment state;
- cancellation boundary;
- delivery deadline;
- late-compensation rule;
- shelf-life guarantee;
- wallet terms;
- customer approvals.

The visual design may remain branded, but transactional meaning must be conventional.

## 59. Post-Checkout

Should unlock:

- household account;
- minimal pet profile;
- immersive order journey;
- wallet;
- missions;
- future-platform preview.

## 60. Order Journey

During normal progress:

- narrative-first;
- visual;
- immersive;
- no unnecessary operational detail.

During exceptions:

- plain language;
- explicit required action;
- deadline and financial consequence;
- customer support path.

---

# Part XIX — Business Metrics

## 61. Primary Commercial Metrics

- completed conversion;
- repeat purchase rate;
- gross margin after import and compensation;
- delivered-within-14-days rate;
- product-level saving;
- cancellation before sourcing;
- sourcing failure rate;
- wallet-credit redemption;
- replenishment reservation approval;
- concierge-request conversion.

## 62. Experience Metrics

- direct-shop versus universe conversion;
- mission completion;
- product discovery depth;
- product-detail views;
- basket attachment;
- pet-profile completion by value event;
- tracking engagement;
- post-checkout activation.

## 63. Supply Metrics

- threshold attainment;
- cost of proceeding below threshold;
- source reliability;
- product-level delivery performance;
- supplier-related failures;
- shelf-life exceptions;
- price-reference accuracy.

---

# Part XX — Risks and Required Validation

## 64. Critical Commercial Risks

- the 14-day firm commitment may be difficult under demand-based import;
- the 5% late credit may materially affect low-margin items;
- proceeding below batch threshold may create recurring losses;
- 50% savings may not be sustainable across the assortment;
- a three-month wallet expiry may affect trust if not communicated well;
- supplier assurance alone is a weak authenticity standard.

## 65. Critical Operational Risks

- international sourcing delays;
- customs or clearance variability;
- exchange-rate movement;
- supplier stock changes;
- inability to verify expiry before purchase;
- heavy-bag logistics;
- household consumption prediction errors;
- late replenishment approval;
- narrative tracking becoming misleading.

## 66. Legal and Compliance Validation Required

Before production launch, specialist review is required for:

- import and resale legality;
- customs handling;
- product registration or labeling;
- veterinary or food-related requirements;
- customer cancellation rights;
- refund obligations;
- claims around authenticity;
- use of market-reference prices;
- wallet-credit expiry;
- personal and pet data handling;
- provider marketplace obligations in later phases.

This document records product decisions. It does not replace legal or regulatory review.

---

# Part XXI — Explicitly Deferred Decisions

The following areas are intentionally not yet locked in implementation detail:

- final brand name;
- final visual language;
- exact names of systems and planets;
- detailed mission taxonomy;
- final open-source commerce stack;
- infrastructure provider;
- payment gateway;
- logistics provider;
- provider onboarding;
- commission and settlement model;
- community features;
- veterinary records;
- service booking;
- loyalty levels;
- wallet-credit consumption priority;
- exact product taxonomy;
- detailed shelf-life discount formula;
- exact definition of sourcing-start event;
- internal loss ceiling for missed batch thresholds.

These should be addressed in future decision records and should not be invented silently during implementation.

---

# Part XXII — Implementation Governance

## 67. Source-of-Truth Rule

Agents and developers should treat this file as the current product baseline.

When implementation conflicts with this document:

1. stop the affected implementation;
2. identify the conflicting decision;
3. propose a specific amendment;
4. receive founder approval;
5. update the decision record;
6. resume implementation.

## 68. No Silent Assumptions

Implementation agents must not silently decide:

- customer financial obligations;
- refund rights;
- order deadlines;
- trust claims;
- product substitutions;
- shelf-life exceptions;
- automatic payments;
- wallet expiry;
- provider access;
- care or health recommendations.

## 69. Decision Amendment Format

Future amendments should include:

```text
Decision ID:
Previous decision:
New decision:
Reason:
Affected flows:
Affected data:
Affected policies:
Migration required:
Approved by:
Approval date:
```

---

# Part XXIII — Current Product Baseline

The current baseline can be summarized as follows:

> A premium, immersive pet-nutrition commerce experience acquires urban Iranian dog and cat owners through supplier-verified products, transparent product-level savings, and a firm 14-day delivery commitment. The platform operates the initial assortment through hybrid demand aggregation and individual sourcing. Checkout activates a household account, progressive pet profiles, wallet, missions, and an immersive order journey. Purchases may belong to one pet, multiple pets, or shared household supply. Consumption is estimated progressively, and replenishment may be reserved 14 days before predicted depletion with explicit customer approval. The shop is the first system in a larger curated pet platform that will eventually coordinate products, services, care journeys, and history around each pet.

---

## 70. Approval Status

All decisions recorded through **Decision 0.43** are treated as approved and locked based on the conversation.

The final decision recorded is:

> Products below the six-month shelf-life threshold may only be offered with exact expiry disclosure, explicit customer approval, and an additional discount.

Any later change should be recorded as a formal amendment rather than silently replacing this baseline.
