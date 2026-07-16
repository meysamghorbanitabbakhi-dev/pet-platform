# K9 migration notes

Base revision: `1da656bcd5e08310596a5c77e5cad4f421e74691`

Alembic head after K9 is `20260716_0021`.

## Revision summary

| Revision | Purpose |
|---|---|
| `20260716_0019` | K9.1 catalog/order/context persistence additions. |
| `20260716_0020` | K9.2 inventory, semantic remaining facts, estimates, reorder and snooze persistence. |
| `20260716_0021` | K9.3 availability subscriptions, support/customer requests, delay acknowledgements, journey check-ins and journey definition snapshots. |

## Operational notes

- K9.4 adds no schema revision. It reconciles acceptance, fixtures, documentation and package contents only.
- K9.4 corrected `20260716_0013` to use Alembic `op.f(...)` for the existing named status check drop. This preserves the intended schema and makes fresh PostgreSQL upgrades deterministic under the repository naming convention.
- Do not rewrite applied revisions. Future migrations must be ordered after `20260716_0021`.
- PostgreSQL upgrade/downgrade/upgrade evidence is required when a safe database environment is available.
- If only static Alembic checks are available, report environment blockage separately rather than claiming live database verification.
