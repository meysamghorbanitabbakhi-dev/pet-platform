# Backend contract blockers

Generated: 2026-07-17, last reconciled 2026-07-18. These are the only states, out of all 152 accepted design
states, classified `BACKEND_BLOCKED` in `design-state-implementation-matrix.md`: either the backend OpenAPI
(`backend/openapi.json`, Alembic head governed by `backend/release-contract.json` — do not hardcode it here)
does not expose the operation or response field the design requires, or (G5-SHOP-13) no approved backend domain
rule exists yet for the frontend to build against. Every other MISSING/PARTIAL state in
`design-state-implementation-matrix.md` is a frontend build gap only — the backend already provides what it needs.

Do not invent a frontend-only workaround for any row below. Continue implementing all unblocked states while
these wait on backend ownership.

---

## G5-SHOP-13 — Product alternatives

- **user_goal**: When a desired product is unavailable or doesn't fit a pet's needs, see other products the platform considers reasonable substitutes.
- **missing_operation**: none exists, and none should be built speculatively. This is not a missing read endpoint so much as a missing domain rule: `gate5.2c-screen-data.v3.1.js` marks this state's disposition `deferred`, and there is no approved definition anywhere in the backend of what makes two products "alternatives" of each other (species match? formula match? weight-range equivalence? price-band equivalence?).
- **required_request_shape/response_shape**: cannot be specified yet — depends on the substitutability rule, which is a product decision, not an engineering one.
- **authorization_scope**: n/a until a rule exists.
- **idempotency_requirement**: n/a (would be a read).
- **policy_requirement**: none identified yet.
- **recommended_backend_owner**: catalog module, pending a product decision on the substitutability rule. Do not infer one from product names/categories on the frontend — that would fabricate a business rule the platform has not approved.

---

## G5-SHOP-14 — Catalog search

- **user_goal**: Find a product by typing a Persian query (title, SKU, product line, or formula) instead of scrolling the full catalog.
- **missing_operation**: a backend-owned search operation, e.g. `GET /api/v1/catalog/offers/search?q=...`. Today only `GET /api/v1/catalog/offers` (full/paginated list, no query-text parameter) exists.
- **required_request_shape**: query string `q` (Persian-normalized), optional availability/species/category filters where the catalog data already supports them, and standard pagination params.
- **required_response_shape**: same bounded, paginated `OfferResponse[]`-shaped list the catalog list endpoint already returns, plus a typed empty-result response (not a bare `[]` the frontend has to interpret).
- **authorization_scope**: same as the existing public catalog list (no additional auth).
- **idempotency_requirement**: n/a (read-only).
- **policy_requirement**: must not expose operator-only price-intelligence fields through this path.
- **recommended_backend_owner**: catalog module — the goal is Persian-normalized, deterministically-ordered, paginated search over the real catalog, not client-side filtering of whichever page of `/shop` happens to already be loaded (which silently misses everything not currently on screen and isn't real search).

---

## G5-AUTH-11 — OTP SMS delivery-failure state

- **user_goal**: Know when an OTP code was requested successfully but the SMS provider (Payamak) failed to deliver it, so the user isn't left waiting on a code that will never arrive.
- **missing_operation**: none exists. `POST /api/v1/auth/otp/request` returns only `{ challenge_id, expires_in_seconds }` (202) or a 422 validation error — there is no delivery-status callback, webhook receiver, or polling endpoint for provider-side delivery confirmation anywhere in `backend/openapi.json`.
- **required_request_shape**: either (a) a provider delivery-status webhook the backend ingests and re-exposes, or (b) a poll endpoint `GET /api/v1/auth/otp/{challenge_id}/delivery-status`.
- **required_response_shape**: `{ challenge_id: string, delivery_state: "sent" | "delivered" | "failed" | "unknown" }`.
- **authorization_scope**: unauthenticated (pre-session, same boundary as the OTP request/verify endpoints themselves) but must be scoped to the issuing `challenge_id` only — must not enumerate other challenges.
- **idempotency_requirement**: polling is naturally idempotent; if webhook-driven, the webhook handler must dedupe by provider delivery-receipt id.
- **policy_requirement**: none — this is a provider-integration gap, not a policy toggle. The design source for this state is marked `"assumed"` in `gate5.2c-screen-data.v3.1.js`, meaning the designer flagged it as unconfirmed rather than backend-verified.
- **vendor decision (recorded 2026-07-18)**: checked against the actual integration, `app/integrations/otp/payamak_panel.py`, and its reference documentation, `backend/docs/integrations/payamak-panel.md`. The only contracted operation is `POST https://rest.payamak-panel.com/api/SendSMS/SendSMS`, which returns a synchronous `{RetStatus, Value}` submission-accepted/-rejected response and nothing else — no delivery receipt (DLR) field, no webhook registration, no polling endpoint is documented or implemented anywhere in this integration. **Conclusion: Payamak Panel, as integrated here, does not support delivery-receipt tracking.** This state stays `BACKEND_BLOCKED` — not because the backend hasn't built a poll/webhook handler yet, but because there is nothing on the provider side for such a handler to consume. Building one now would be speculative, contradicting the "no new product decision" rule. If delivery tracking becomes a real requirement, it requires either a different SMS provider or a commercial upgrade with Payamak, both genuine vendor/product decisions outside engineering scope. In the meantime, product copy for OTP request screens should say only that the request was submitted, not that delivery is confirmed — checked 2026-07-18: the current /auth/otp copy ("کد ۶ رقمی پیامک‌شده را وارد کنید") already only prompts for the code and makes no delivery guarantee, so no copy change was needed.
- **recommended_backend_owner**: auth/OTP module, in coordination with whichever integration owns the Payamak SMS provider client (`app/integrations/otp/`) — requires a genuine product/vendor decision (a different or upgraded SMS provider), so this is explicitly **not** something to build speculatively per the "no new product decision" rule; flagging only.

---

## Explicitly not blocked (checked and ruled out)

A few states looked backend-blocked at first glance but are not, for the record:

- **G5-CHK-13/14/15 (payment cancelled vs. failed vs. ambiguous)**: the Zarinpal callback route (`app/api/routes/commerce.py`) intentionally returns one merged `cancelled_or_failed` state. This matches `GATE52C_RESIDUAL` #1 ("Uncertain payment... Calm pending-verification state; never routes directly to retry") — an accepted design limitation, not a missing operation, and not a backend blocker. As of the 2026-07-18 matrix reconciliation, G5-CHK-13 is IMPLEMENTED (it represents the real merged screen) and G5-CHK-14 is OBSOLETE_BY_CONTRACT (superseded by CHK-13 — the provider genuinely cannot support a second, separately-toned state). G5-CHK-15's remaining gap (no nav-to-order/support-contact link on ambiguous verification failure) stays PARTIAL — that one is a real frontend build gap, tracked in the matrix, not here.
- **G5-ACC-02/07/10/14 (pet list, wallet, notification inbox, privacy export)**: all have real, working backend operations (`GET .../pets`, `GET .../wallet`, `GET .../notifications`, `GET /privacy/export`) that are simply unconsumed by any frontend code today. These are Wave 5/7 build work, not backend blockers.
- **All of JOURNEY-05 through JOURNEY-20 and BRIDGE-25 through BRIDGE-35 (care journeys, reorder, Garden)**: every backend operation these states need already exists and is policy-enabled (`care_journey_delivery_enabled=true`, `semantic_level_estimation_enabled=true`). Zero frontend code consumes any of them today. Wave 1/2/3 build work, not backend blockers.
- **G5-ACC-03 (address edit/delete)**: closed 2026-07-18. `PATCH`/`DELETE /api/v1/pet-life/households/{household_id}/addresses/{address_id}` now exist (non-enumerating 404s, idempotent soft-delete through `active`, immutable order snapshots preserved — orders copy address fields into `delivery_address_snapshot` at checkout time and never hold a live reference), and `/account` has real edit/delete Sheets wired to them. No longer blocked; removed from the list above.
- **G5-ACC-06 (SMS / quiet-hours preference read-back)**: closed 2026-07-18. `GET /api/v1/pet-life/notifications/preferences/{event_key}/sms` now exists, returning the same typed shape the existing `PUT` persists (empty/default when no row exists yet — `sms_enabled=true`, matching the model column default; a real value once one exists, including correctly round-tripping an overnight quiet-hours window like 22:30→07:00). `/account/notifications/preferences` reads and writes it for the one real SMS-preference-gated event (`wallet.late_delivery_credit_granted`), hidden behind the `late_credit_customer_visible` policy gate like every other disabled-by-policy feature. No longer blocked; removed from the list above.
- **G5-ACC-13 (notification destination/deep-link field)**: closed 2026-07-18. `NotificationListItem.destination: { kind, id }` now exists (migration `20260718_0026` adds `destination_kind`/`destination_id` to `notifications_notifications`), populated server-side at notification-creation time for both real notification-creating paths (`catalog.offer_available` → `offer`, `wallet.late_delivery_credit_granted` → `order`). The inbox deep-links through an explicit allowlisted route mapper (`src/lib/notification-destination.ts`) — never by parsing `event_key` or trusting a backend-supplied URL. The kind enum was extended with `offer` beyond what this entry originally proposed (`order | inventory_unit | journey | none`): `catalog.offer_available` is the only other real notification-creating path today and genuinely has no home among the original four. `inventory_unit`/`journey`/`customer_request` remain valid kinds for forward-compatibility but nothing populates them yet, since no notification-creation code exists for those events. Existing/legacy rows correctly read back as `{kind: "none", id: null}` via the column default. No longer blocked; removed from the list above.
- **G5-ACC-16 (customer-facing privacy-request status read-back)**: closed 2026-07-18. Customer-scoped `GET /api/v1/privacy/requests` (paginated) and `GET /api/v1/privacy/requests/{request_id}` (non-enumerating — identical 404 for "belongs to another identity" and "does not exist") now exist, exposing `PrivacyRequestResponse{id, request_type, status, created_at, completed_at}` with typed `status`/`request_type` enums. `/account/privacy` shows a persistent request list surviving reload; the existing POST dedup behavior (one active request per type) now correctly shows as one row after a refetch, not two. No longer blocked; removed from the list above.
