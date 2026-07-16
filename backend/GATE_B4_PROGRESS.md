# Gate B4 — Order Operations

## Implemented

- The scheduler finds overdue eligible orders and creates missing late-delivery credits.
- Credit creation remains idempotent through a unique order source and row locking.
- Credit events enter the transactional outbox for future SMS/in-app notification delivery.
- Customer order history includes literal IRR totals, commitment dates, delivery dates, and status.
- Customer order journey exposes factual payment and fulfillment events without internal reasons.
- Refund, replacement, and substitution proposals are stored as `awaiting_policy` only.
- No resolution execution endpoint exists before an approved policy version is supplied.
- The operator 360-degree view joins households, pets, orders, payment count, inventory count,
  journey count, and available wallet balance.
- Today prioritizes sourcing failure, overdue delivery, and delayed delivery ahead of food setup,
  journey, and Garden presence.
- Migration `20260716_0005` is the sole Alembic head.

## Deferred by founder instruction

- Docker Compose PostgreSQL/Redis runtime and concurrency validation.

## Next slice

- Notification preferences, templates, delivery attempts, and quiet-hours policy.
- Outbox handlers for OTP-independent transactional SMS and in-app notifications.
- Operator resolution-policy registry once refund/replacement/substitution rules are approved.
- Catalogue trust and shelf-life evidence records.
- Exact sourced-unit expiry disclosure after sourcing confirmation.
