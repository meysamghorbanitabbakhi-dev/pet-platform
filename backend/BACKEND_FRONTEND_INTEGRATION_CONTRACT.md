# Backend/frontend integration contract

Base revision: `1da656bcd5e08310596a5c77e5cad4f421e74691`

The checked OpenAPI artifact at `docs/api/openapi.json` is authoritative. The frontend must not invent price, delivery, trust, portion, policy or compensation facts.

## Intent classification

| UI intent | Classification | Backend contract |
|---|---|---|
| Bootstrap context | endpoint-backed | `GET /api/v1/me/context` |
| Pet switcher | endpoint-backed | `GET /api/v1/pet-life/households/{household_id}/pets` |
| Offer trust detail | endpoint-backed | `GET /api/v1/catalog/offers/{offer_id}` |
| Checkout full payment | endpoint-backed | `POST /api/v1/checkout/orders` |
| Payment redirect | endpoint-backed | `POST /api/v1/orders/{order_id}/payments/zarinpal` |
| Payment callback | endpoint-backed | `GET /api/v1/payments/zarinpal/callback` |
| Reload order | endpoint-backed | `GET /api/v1/orders/{order_id}` |
| Order journey | endpoint-backed | `GET /api/v1/orders/{order_id}/journey` |
| Order pet planning | endpoint-backed | `PUT /api/v1/orders/{order_id}/pet-plan` |
| Household inventory detail | endpoint-backed | `GET /api/v1/pet-life/inventory/{unit_id}` |
| External inventory | endpoint-backed | `POST /api/v1/pet-life/households/{household_id}/inventory/external` |
| Exact-grams opening | endpoint-backed | `POST /api/v1/pet-life/inventory/{unit_id}/open` |
| Semantic-level opening | policy-gated | Same endpoint, stable `semantic_level_policy_disabled` while bounds are unapproved |
| Reorder assessment | endpoint-backed | `POST /api/v1/pet-life/inventory/{unit_id}/reorder-assessment` |
| Reorder snooze | endpoint-backed | `PUT /api/v1/pet-life/inventory/{unit_id}/reorder-snooze` |
| Today hub | endpoint-backed | `GET /api/v1/pet-life/pets/{pet_id}/today` |
| Availability subscribe/cancel | endpoint-backed | `POST/DELETE /api/v1/catalog/offers/{offer_id}/availability-subscriptions` |
| Availability subscription list | endpoint-backed | `GET /api/v1/me/availability-subscriptions` |
| Customer support/concierge request | endpoint-backed | `POST /api/v1/customer-requests` |
| Request history/detail | endpoint-backed | `GET /api/v1/customer-requests`, `GET /api/v1/customer-requests/{request_id}` |
| Delay acknowledgement | endpoint-backed | `POST /api/v1/orders/{order_id}/delay-acknowledgements` |
| Journey discovery/detail/check-in | policy-gated | `care_journey_delivery_enabled=false` until approved |
| Diary detail | endpoint-backed | `GET /api/v1/pet-life/pets/{pet_id}/diary/{entry_id}` |
| Garden state/place/store | endpoint-backed | `GET /api/v1/pet-life/pets/{pet_id}/garden`, `PUT/DELETE /api/v1/pet-life/garden/{reward_id}/placement` |
| Reserve now | policy-gated | No executable customer endpoint |
| Self-service refund/replacement/substitution | policy-gated | No executable customer endpoint |
| Push notifications | deferred | K9 only claims in-app and SMS notifications |
| Client-side route cache and animation state | frontend-local | No backend state |

Result: zero unexplained intents.

## Frontend invariants

- Money fields ending in `_irr` are canonical integer IRR.
- Supplier identity and filesystem paths are never frontend facts.
- Incoming Today food appears only for planned pets.
- Unopened and incoming food states have no remaining-days value.
- Unknown shares never produce pet-level remaining-days numbers.
- Availability subscriptions always return `order_created=false`.
- Delay acknowledgement never implies compensation, cancellation, waiver or resolution.
- Garden unlock/placement state is server-derived; no XP, streaks, decay or purchase rewards.
