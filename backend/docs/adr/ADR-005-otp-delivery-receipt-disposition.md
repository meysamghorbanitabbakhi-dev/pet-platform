# ADR-005 — OTP delivery-receipt disposition for the current provider

**Status:** Approved
**Date:** 2026-07-19

## Context

`G5-AUTH-11` ("OTP SMS delivery-failure state") asks the customer-facing OTP screen to
distinguish "code sent" from "code delivered" / "delivery failed". Payamak Panel, as integrated
in `app/integrations/otp/payamak_panel.py` and documented in
`backend/docs/integrations/payamak-panel.md`, exposes exactly one operation:
`POST https://rest.payamak-panel.com/api/SendSMS/SendSMS`, returning a synchronous
`{RetStatus, Value}` submission-accepted/-rejected result. It has no delivery-receipt (DLR)
field, no webhook registration, and no polling endpoint of any kind.

## Decision

`G5-AUTH-11` is formally superseded for the current provider, not merely deferred:

- The backend records and exposes only synchronous submission acceptance or rejection
  (`OtpChallenge.delivery_status` in `pending | sent | failed`), never a post-submission
  delivery outcome.
- Product copy and API responses use "submitted"/"sent" or "unknown" language and must never
  claim "delivered" for SMS. Confirmed 2026-07-19: `/auth/otp` copy ("کد ۶ رقمی پیامک‌شده را
  وارد کنید" and the new sending-transition copy "در حال ارسال کد تایید به ... هستیم") only
  describes sending, not delivery confirmation.
- No delivery-status polling endpoint or webhook receiver is implemented against this provider.
  Building one would fabricate a capability the vendor does not offer.
- `OtpProvider` (`app/integrations/otp/port.py`) gains a `supports_delivery_receipts: bool`
  capability flag, `False` for both `PayamakPanelOtpProvider` and `ConsoleOtpProvider`. A future
  provider that can report real delivery receipts sets this `True` and updates the *same*
  `OtpChallenge` row's delivery fields through the existing `OtpService` — challenge issuance,
  hashing, and verification ownership do not change. Signed webhook ingestion, receipt
  deduplication, challenge-scoped polling, and non-enumerating access are explicitly out of
  scope until such a provider is actually integrated (see
  `frontend/docs/backend-contract-blockers.md#g5-auth-11`).

## Consequences

- `G5-AUTH-11` reclassifies `BACKEND_BLOCKED` → `OBSOLETE_BY_CONTRACT` in
  `frontend/docs/design-state-implementation-matrix.md`. Authority: this ADR. Rationale: the
  design source models a delivery-failure state that no integrated provider can report; treating
  it as a backend build gap ("not built yet") was inaccurate — there is nothing for the backend
  to build against today.
- Switching SMS providers, or a commercial upgrade with Payamak that adds DLR support, is a
  genuine vendor/product decision outside engineering scope and requires its own ADR before any
  receipt-ingestion code is written.
