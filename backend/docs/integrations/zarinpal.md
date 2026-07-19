# Zarinpal payment gateway

The adapter follows Zarinpal Payment Gateway v4 official documentation:

- request: `POST /pg/v4/payment/request.json`;
- redirect: `/pg/StartPay/{authority}`;
- verify: `POST /pg/v4/payment/verify.json`;
- inquiry: `POST /pg/v4/payment/inquiry.json`;
- reverse: `POST /pg/v4/payment/reverse.json`.

## Platform decisions

- Send `currency=IRR`; backend money remains integer IRR.
- Store the `authority` as provider reference before redirecting.
- Treat callback `Status=OK` only as permission to call verify, never as proof of payment.
- Treat verify code `100` as newly verified and `101` as already verified; both are successful,
  idempotent outcomes.
- Persist `ref_id`, masked card, card hash, fee, and the exact verified amount.
- Inquiry is reconciliation evidence only and never replaces verify.
- Reverse is a narrow provider capability available only within the documented time window and
  requires terminal IP configuration. It is not the platform's general refund workflow.
- Provider error codes are translated to canonical errors; raw payloads are not shown to users.

## Environments

Production base URL: `https://payment.zarinpal.com`  
Sandbox base URL: `https://sandbox.zarinpal.com`

Sandbox accepts any UUID-shaped merchant ID and returns authorities beginning with `S`. Real
credentials remain environment variables and are never committed.

## Sources

- https://www.zarinpal.com/docs/paymentGateway/connectToGateway
- https://www.zarinpal.com/docs/paymentGateway/sandBox
- https://www.zarinpal.com/docs/paymentGateway/errorList
- https://www.zarinpal.com/docs/paymentGateway/otherMethods/Inquiry
- https://www.zarinpal.com/docs/paymentGateway/moreFeatures/reverse
