# Provider certification

Run this checklist first in provider sandbox/staging and then once with a controlled production
transaction. Never paste API keys, OTPs, card data, or full provider payloads into tickets or logs.

## Zarinpal

- Confirm the merchant identifier and callback domain are approved.
- Request a payment and follow only the server-returned redirect URL.
- Verify a successful callback server-side and confirm one sourcing job is created.
- Replay the callback; order and payment facts must remain unchanged.
- Exercise cancelled, invalid-authority, failed-verification, timeout, and later reconciliation.
- Confirm no sourcing starts before verified full payment.

## Payamak Panel

- Confirm sender number, credentials, encoding, and Persian delivery behavior.
- Generate an OTP, verify its TTL, resend cooldown, attempt cap, and one-time consumption.
- Exercise wrong, expired, replayed, rate-limited, provider-timeout, and provider-failure cases.
- Confirm logs contain correlation/provider references but never OTP plaintext or credentials.

Record environment, timestamp, application revision, provider reference, expected result, actual
result, and approver. Redact personal and secret data before retaining evidence.
