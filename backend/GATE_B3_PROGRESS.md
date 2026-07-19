# Gate B3 — Operational Control and Today

## Implemented

- Orders now belong explicitly to a household as well as the purchasing identity.
- Fulfillment uses an explicit transition map with append-only operator events.
- Orders cannot jump directly from paid to delivered.
- Delivery records the actual delivery timestamp before inventory projection.
- Journey definitions begin as drafts and require audited operator approval.
- Approval requires a server-configured Garden reward; customers cannot choose objects.
- Late-delivery credits are exactly 5% of merchandise value, idempotent per order.
- Credits expire after three calendar months.
- Wallet debits allocate against the earliest-expiring available credit first.
- Customer wallet balance excludes expired credits.
- Today is a read model ordered around pet identity, food state, next action, active journey,
  and compact Garden presence.
- Today never asks for routine daily feeding logs.
- Migration `20260716_0004` is the sole Alembic head.

## Deferred by founder instruction

- Docker Compose PostgreSQL/Redis runtime and concurrency validation.

## Next slice

- Automated overdue-order credit scheduler and notifications.
- Fulfillment resolution records for refund, replacement, and substitution once policies are approved.
- Order timeline and operator 360-degree read APIs.
- Customer order history and factual order-journey API.
- Today prioritization when food, journey, and order exceptions compete.
