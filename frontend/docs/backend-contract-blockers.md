# Backend contract blockers

Generated: 2026-07-17. These are the only states, out of all 152 accepted design states, where the current
backend OpenAPI (`backend/openapi.json`, alembic head `20260716_0024`, matching `backend/release-contract.json`)
does not expose the operation or response field the design requires. Every other MISSING/PARTIAL state in
`design-state-implementation-matrix.md` is a frontend build gap only — the backend operation already exists.

Do not invent a frontend-only workaround for any row below. Continue implementing all unblocked states while
these wait on backend ownership.

---

## G5-ACC-06 — SMS / quiet-hours preference read-back

- **user_goal**: See the current SMS-notification and quiet-hours preference for a given `event_key` before changing it, so the settings screen can show current state instead of a blind write form.
- **missing_operation**: `GET /api/v1/pet-life/notifications/preferences/{event_key}/sms` (only `PUT` exists today).
- **required_request_shape**: path param `event_key: string`; no body.
- **required_response_shape**: an `SmsPreferenceResponse` with at minimum `{ event_key: string, sms_enabled: boolean, quiet_hours_start: string | null, quiet_hours_end: string | null }`. Quiet-hours read-back was already flagged as an accepted gap in the design package itself (`GATE52C_RESIDUAL` #3: "No GET exists in checked K9 openapi.json. Launch-hidden/deferred.") — this row formalizes that residual note.
- **authorization_scope**: household/pet-owner identity scope (same auth boundary as the existing `PUT` on this path).
- **idempotency_requirement**: none (GET is naturally idempotent).
- **policy_requirement**: gated behind `push_notifications_enabled` only insofar as push channel toggles are shown in the same settings screen; SMS preference itself is not policy-disabled today.
- **recommended_backend_owner**: notifications module (same owner as the existing `PUT .../preferences/{event_key}/sms` in `app/api/routes/pet_life.py`) — add a paired `GET` returning the same preference row the `PUT` already persists.

---

## G5-ACC-13 — Notification destination/deep-link field

- **user_goal**: Tap a notification in the inbox and land on the specific order/inventory/journey screen it refers to, instead of a dead-end inbox row.
- **missing_operation**: not a new endpoint — `GET /api/v1/pet-life/notifications` and `GET /api/v1/pet-life/notifications/feed` exist, but `NotificationListItem` has no field describing where the notification should route to.
- **required_request_shape**: n/a (existing list/feed operations).
- **required_response_shape**: add a typed destination field to `NotificationListItem`, e.g. `destination: { kind: "order" | "inventory_unit" | "journey" | "none", id: string | null }` alongside the existing `{ id, event_key, payload, created_at, read_at }`. `payload` is currently an opaque object; do not have the frontend parse `event_key` strings to guess a route — that would be client-invented routing logic.
- **authorization_scope**: same as existing notification list endpoints (pet/household-owner scope).
- **idempotency_requirement**: none (read-only).
- **policy_requirement**: none beyond existing `push_notifications_enabled` gating of the channel that generates these notifications in the first place.
- **recommended_backend_owner**: notifications module — the destination is knowable server-side at notification-creation time (it already knows which order/unit/journey triggered the event), so this is a thin, unambiguous addition to an existing typed response, not a new product decision.

---

## G5-ACC-16 — Customer-facing privacy-request status read-back

- **user_goal**: Come back to the privacy/account screen later and see whether a previously submitted disable/anonymize request is still pending, in review, or has been actioned, instead of only ever seeing the one-time creation response.
- **missing_operation**: `GET /api/v1/privacy/requests` (customer-scoped) or `GET /api/v1/privacy/requests/{request_id}`. Only `POST /api/v1/privacy/requests` (customer, returns `PrivacyRequestResponse{id, status}` once) and `GET /api/v1/operator/privacy/requests` + `POST /api/v1/operator/privacy/requests/{request_id}/disable` (operator-only) exist today.
- **required_request_shape**: none (GET) or `request_id` path param for the single-request variant.
- **required_response_shape**: `PrivacyRequestResponse` (already defined: `{ id: string, status: string }`) or a page of them — the shape already exists, it's just not exposed to the customer identity.
- **authorization_scope**: customer identity scope, restricted to requests the caller's own identity created (must not enumerate other households' requests).
- **idempotency_requirement**: none (read-only).
- **policy_requirement**: none.
- **recommended_backend_owner**: privacy module — the operator-facing list/detail already exists on the same underlying table; this is a thin customer-scoped read exposure of data the backend already tracks, not a new product decision. Until this exists, the frontend shows the immediate creation response only (`frontend/src/features/privacy/privacy-center.tsx`) and cannot show status after a page reload or on a later visit.

---

## G5-AUTH-11 — OTP SMS delivery-failure state

- **user_goal**: Know when an OTP code was requested successfully but the SMS provider (Payamak) failed to deliver it, so the user isn't left waiting on a code that will never arrive.
- **missing_operation**: none exists. `POST /api/v1/auth/otp/request` returns only `{ challenge_id, expires_in_seconds }` (202) or a 422 validation error — there is no delivery-status callback, webhook receiver, or polling endpoint for provider-side delivery confirmation anywhere in `backend/openapi.json`.
- **required_request_shape**: either (a) a provider delivery-status webhook the backend ingests and re-exposes, or (b) a poll endpoint `GET /api/v1/auth/otp/{challenge_id}/delivery-status`.
- **required_response_shape**: `{ challenge_id: string, delivery_state: "sent" | "delivered" | "failed" | "unknown" }`.
- **authorization_scope**: unauthenticated (pre-session, same boundary as the OTP request/verify endpoints themselves) but must be scoped to the issuing `challenge_id` only — must not enumerate other challenges.
- **idempotency_requirement**: polling is naturally idempotent; if webhook-driven, the webhook handler must dedupe by provider delivery-receipt id.
- **policy_requirement**: none — this is a provider-integration gap, not a policy toggle. The design source for this state is marked `"assumed"` in `gate5.2c-screen-data.v3.1.js`, meaning the designer flagged it as unconfirmed rather than backend-verified.
- **recommended_backend_owner**: auth/OTP module, in coordination with whichever integration owns the Payamak SMS provider client (`app/integrations/`) — requires a genuine product/vendor decision (webhook vs. poll, and whether Payamak's API even exposes delivery receipts), so this is explicitly **not** something to build speculatively per the "no new product decision" rule; flagging only.

---

## Explicitly not blocked (checked and ruled out)

A few states looked backend-blocked at first glance but are not, for the record:

- **G5-CHK-13/14/15 (payment cancelled vs. failed vs. ambiguous)**: the Zarinpal callback route (`app/api/routes/commerce.py`) intentionally returns one merged `cancelled_or_failed` state. This matches `GATE52C_RESIDUAL` #1 ("Uncertain payment... Calm pending-verification state; never routes directly to retry") — an accepted design limitation, not a missing operation. Frontend gap (distinct tone/copy per case) is tracked as PARTIAL in the matrix, not here.
- **G5-ACC-02/07/10/14 (pet list, wallet, notification inbox, privacy export)**: all have real, working backend operations (`GET .../pets`, `GET .../wallet`, `GET .../notifications`, `GET /privacy/export`) that are simply unconsumed by any frontend code today. These are Wave 5/7 build work, not backend blockers.
- **All of JOURNEY-05 through JOURNEY-20 and BRIDGE-25 through BRIDGE-35 (care journeys, reorder, Garden)**: every backend operation these states need already exists and is policy-enabled (`care_journey_delivery_enabled=true`, `semantic_level_estimation_enabled=true`). Zero frontend code consumes any of them today. Wave 1/2/3 build work, not backend blockers.
