# API endpoint catalog

The checked OpenAPI contract contains 133 public operations. Routes use the `/api/v1` prefix except health/docs/internal metrics. Schema details in `docs/api/openapi.json` are authoritative.

## K9 customer integration endpoints

| Method | Endpoint | Capability |
|---|---|---|
| GET | `/me/context` | New-device identity, household, pet, onboarding and capability reconstruction |
| GET | `/pet-life/households/{household_id}/pets` | Deterministic active household pet switcher |
| GET | `/catalog/offers/{offer_id}` | Typed offer detail with Persian content, IRR price, trust and availability |
| GET | `/orders/{order_id}` | Reload-safe typed order detail |
| PUT | `/orders/{order_id}/pet-plan` | Idempotent complete replacement of planned pets for order lines |
| POST | `/orders/{order_id}/delay-acknowledgements` | Idempotently acknowledge visible delivery delay with no compensation implication |
| GET | `/pet-life/inventory/{unit_id}` | Rich household inventory detail with assignments and active estimate |
| POST | `/pet-life/inventory/{unit_id}/reorder-assessment` | Authoritative reorder recommendation from server facts and 3-day safety buffer |
| PUT | `/pet-life/inventory/{unit_id}/reorder-snooze` | Durable 72-hour maximum reorder snooze with approved early-break rule |
| GET | `/pet-life/pets/{pet_id}/today` | Typed Today projection with discriminated food state |
| POST | `/catalog/offers/{offer_id}/availability-subscriptions` | Idempotent availability subscription; never creates commercial records |
| DELETE | `/catalog/offers/{offer_id}/availability-subscriptions` | Idempotent availability cancellation |
| GET | `/me/availability-subscriptions` | Customer availability subscription list |
| POST | `/customer-requests` | Idempotent support/concierge request with no promises |
| GET | `/customer-requests` | Customer request list |
| GET | `/customer-requests/{request_id}` | Customer request detail |
| GET | `/pet-life/pets/{pet_id}/journey-offers` | Approved journey offers; policy-gated |
| GET | `/pet-life/journey-definitions/{definition_id}` | Approved versioned journey detail; policy-gated |
| GET | `/pet-life/journeys/{journey_id}` | Journey detail with ordered check-ins; policy-gated |
| POST | `/pet-life/journeys/{journey_id}/check-ins` | Durable validated journey check-in; policy-gated |
| GET | `/pet-life/pets/{pet_id}/diary/{entry_id}` | Typed diary entry detail |
| GET | `/pet-life/pets/{pet_id}/garden` | Server-derived Garden state |
| PUT | `/pet-life/garden/{reward_id}/placement` | Place/move Garden reward |
| DELETE | `/pet-life/garden/{reward_id}/placement` | Store Garden reward while preserving linked memory |

## Existing customer foundations

| Area | Key endpoints |
|---|---|
| Auth | `POST /auth/otp/request`, `POST /auth/otp/verify`, `POST /auth/session/refresh`, `POST /auth/session/logout` |
| Commerce | `GET /catalog/offers`, `POST /checkout/orders`, `POST /orders/{order_id}/payments/zarinpal`, `GET /payments/zarinpal/callback`, `GET /orders`, `GET /orders/feed`, `GET /orders/{order_id}/journey` |
| Household/Pet Life | Household/address/pet creation, external inventory, assignments, opening/correction/exhaust, wallet, notifications, journeys, diary and Garden |
| Pet profile/health/assets | Profile, breed selection, measurements, reminders, consents, private assets, body assessments and approved care guidance |
| Knowledge/privacy/system | Breed knowledge, pet knowledge, privacy export/request, policy read, health and metrics |

## K9 operator endpoints

| Method | Endpoint | Capability |
|---|---|---|
| PUT | `/operator/offers/{offer_id}/capacity` | Updates capacity and emits replay-safe availability notifications when genuinely available |
| GET | `/operator/customer-requests` | Operator customer request queue |
| POST | `/operator/customer-requests/{request_id}/status` | Audited request status transition |
| Existing | Catalog, sourcing, fulfillment, trust, journey-definition, notification, knowledge, privacy and telemetry endpoints | K8 behavior preserved |

## Policy-hidden customer capabilities

There are no executable customer endpoints for reserve-now, self-service cancellation after sourcing, refund, replacement, substitution or delay compensation. Push notifications are not claimed in K9.
