# Gate B1 — Transactional Commerce Progress

## Completed

- OTP verification now issues opaque access and rotating refresh tokens.
- Sessions store only keyed token hashes and support expiry, refresh, and logout.
- Catalogue suppliers, products, and sourced-after-payment offers are modeled.
- Checkout uses active server-side offer prices and immutable IRR line snapshots.
- Checkout and payment initiation have scoped idempotency keys.
- Zarinpal payment request and callback endpoints use the official v4 adapter.
- A callback never proves payment; only server-side verification advances an order.
- Verified payment freezes the paid timestamp and exact 366-hour commitment.
- Verified payment creates a single sourcing job and an outbox event.
- Full payment is the only enabled path; reserve-now remains disabled.
- Migration `20260716_0002` is the sole Alembic head.
- OTP requests are rate-limited by hashed mobile, IP, and optional device identifier.
- The single operator can create suppliers, products, and offers with mandatory reasons and audit records.
- Operator-triggered Zarinpal inquiry reconciles uncertain payment attempts without treating inquiry as verification.

## Required before Gate B1 approval

- Database-backed concurrency and Compose validation are founder-accepted as deferred.
- Test duplicate callbacks racing in separate transactions.
- Exercise Zarinpal sandbox when a sandbox/merchant credential is available.

No production claims should be made from the contract-mocked provider tests alone.
