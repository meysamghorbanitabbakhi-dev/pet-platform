# Gate B2 — Pet Life Foundation

## Implemented

- Household is the ownership and shared-inventory boundary.
- Pets belong to households; inventory does not belong directly to a pet.
- Platform-order and external-purchase inventory sources are supported.
- Inventory remains unopened until an explicit opening action.
- Consumption assignments can target one or multiple pets, with unknown shares supported.
- Food estimates cannot start without opening; unknown portions produce an explicit unknown range.
- Journey definitions are immutable by version and start only when approved.
- Journey completion atomically creates a diary memory and one eligible Garden reward.
- Garden reward sources exclude purchases, visits, recap reads, taps, streaks, and spending.
- Migration `20260716_0003` is the sole Alembic head.

## Application APIs completed

- Household and pet commands with membership authorization.
- Idempotent delivered-order-to-household-inventory projection.
- External inventory, assignment, opening, correction, and exhaustion endpoints.
- Journey start, pause, resume, stop, and completion endpoints.
- Diary reads and Garden reads/placement.
- Reorder assessment using pessimistic food range, latest delivery, and safety buffer.

## Next implementation slice

- Operator approval workflow for versioned care content.
- Fulfillment state transitions and exception resolution.
- Late-delivery credit and earliest-expiry wallet ledger.
- Today read model joining pet, food, next action, journey, and compact Garden state.

PostgreSQL/Redis Compose and concurrency validation remain founder-accepted as deferred.
