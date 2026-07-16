# API endpoint catalog

The checked OpenAPI contract contains 110 public operations. Unless stated otherwise, application
routes use the `/api/v1` prefix and bearer authentication where the OpenAPI security declaration
requires it. Request/response schemas and validation constraints are authoritative in
`docs/api/openapi.json`.

## Authentication

| Method | Endpoint | Capability |
|---|---|---|
| POST | `/auth/otp/request` | Generate and send an OTP under mobile, device and IP throttles |
| POST | `/auth/otp/verify` | Validate OTP and establish access/refresh session |
| POST | `/auth/session/refresh` | Rotate/refresh an authenticated session |
| POST | `/auth/session/logout` | Revoke the active session |

## Commerce and orders

| Method | Endpoint | Capability |
|---|---|---|
| GET | `/catalog/offers` | Browse available platform-owned offers |
| POST | `/checkout/orders` | Create a full-payment IRR order |
| POST | `/orders/{order_id}/payments/zarinpal` | Initiate Zarinpal payment |
| GET | `/payments/zarinpal/callback` | Receive and verify payment callback |
| GET | `/orders` | Paginated customer order list |
| GET | `/orders/feed` | Signed-cursor customer order feed |
| GET | `/orders/{order_id}/journey` | Factual order status and events |

## Household and Pet Life

| Method | Endpoint | Capability |
|---|---|---|
| POST | `/pet-life/households` | Create household and owner membership |
| POST | `/pet-life/households/{household_id}/addresses` | Create delivery address |
| GET | `/pet-life/households/{household_id}/addresses` | List active addresses |
| POST | `/pet-life/households/{household_id}/pets` | Create dog/cat profile |
| POST | `/pet-life/households/{household_id}/inventory/external` | Record externally purchased inventory |
| GET | `/pet-life/households/{household_id}/inventory` | List shared household inventory |
| PUT | `/pet-life/inventory/{unit_id}/assignments` | Assign one unit to one or more pets |
| POST | `/pet-life/inventory/{unit_id}/open` | Confirm opening and establish estimate inputs |
| POST | `/pet-life/inventory/{unit_id}/estimate/correct` | Correct an active estimate |
| POST | `/pet-life/inventory/{unit_id}/exhaust` | Mark inventory exhausted |
| POST | `/pet-life/reorder/assess` | Calculate transparent reorder timing |
| GET | `/pet-life/pets/{pet_id}/today` | Build the pet-centered Today hub |
| POST | `/pet-life/pets/{pet_id}/journeys` | Explicitly start approved journey |
| POST | `/pet-life/journeys/{journey_id}/pause` | Pause journey |
| POST | `/pet-life/journeys/{journey_id}/resume` | Resume journey |
| POST | `/pet-life/journeys/{journey_id}/stop` | Stop journey with reason |
| POST | `/pet-life/journeys/{journey_id}/complete` | Complete journey and create memory/reward |
| GET | `/pet-life/pets/{pet_id}/diary` | List durable diary memories |
| GET | `/pet-life/pets/{pet_id}/garden` | List Garden rewards and placement |
| PUT | `/pet-life/garden/{reward_id}/placement` | Place/move an eligible Garden object |
| GET | `/pet-life/households/{household_id}/wallet` | Read household wallet balance |
| GET | `/pet-life/notifications` | Paginated notification inbox |
| GET | `/pet-life/notifications/feed` | Signed-cursor notification feed |
| POST | `/pet-life/notifications/{notification_id}/read` | Mark notification read |
| PUT | `/pet-life/notifications/preferences/{event_key}/sms` | Configure event-level SMS preference |

## Pet profile, health and guidance

| Method | Endpoint | Capability |
|---|---|---|
| GET | `/pet-life/pets/{pet_id}/profile` | Read progressive profile |
| PATCH | `/pet-life/pets/{pet_id}/profile` | Update permitted profile fields |
| PUT | `/pet-life/pets/{pet_id}/breed-selection` | Select known/mixed/unknown breed state |
| GET | `/pet-life/pets/{pet_id}/breed-selection/history` | Read immutable selection history |
| GET | `/pet-life/pets/{pet_id}/profile-completeness` | Optional completeness and next prompt |
| POST | `/pet-life/pets/{pet_id}/measurements` | Record owner-reported measurement |
| POST | `/pet-life/pets/{pet_id}/measurements/{measurement_id}/corrections` | Append measurement correction |
| GET | `/pet-life/pets/{pet_id}/measurements` | List measurement history |
| GET | `/pet-life/pets/{pet_id}/measurements/{measurement_id}/reference-comparison` | Safe approved reference comparison |
| GET | `/pet-life/pets/{pet_id}/weight-trend` | Calculate personal weight trend |
| POST | `/pet-life/pets/{pet_id}/measurement-reminders` | Create measurement reminder |
| POST | `/pet-life/pets/{pet_id}/measurement-reminders/{reminder_id}/{action}` | Complete/dismiss reminder action |
| GET | `/pet-life/pets/{pet_id}/care-guidance` | Read eligible approved guidance feed |
| PUT | `/pet-life/pets/{pet_id}/care-guidance/{guidance_id}/preference` | Dismiss, snooze or restore guidance |

## Private pet assets and assessments

| Method | Endpoint | Capability |
|---|---|---|
| POST | `/pet-life/pets/{pet_id}/consents` | Grant versioned purpose-specific consent |
| POST | `/pet-life/pets/{pet_id}/consents/{consent_id}/withdraw` | Withdraw consent and active use |
| POST | `/pet-life/pets/{pet_id}/assets` | Upload medical/body photograph or document |
| GET | `/pet-life/pets/{pet_id}/assets` | List authorized private assets |
| GET | `/pet-life/pets/{pet_id}/assets/{asset_id}` | Download authorized private asset |
| DELETE | `/pet-life/pets/{pet_id}/assets/{asset_id}` | Remove asset subject to retention policy |
| POST | `/pet-life/pets/{pet_id}/body-assessments` | Record owner-reported BCS/MCS assessment |
| GET | `/pet-life/pets/{pet_id}/body-assessments` | List assessment history |

## Public and pet-specific knowledge

| Method | Endpoint | Capability |
|---|---|---|
| GET | `/knowledge/breeds` | List current approved Persian breeds |
| GET | `/knowledge/search` | Persian-normalized breed/alias search |
| GET | `/knowledge/breeds/{breed_id}` | Approved breed detail and citations |
| GET | `/knowledge/pets/{pet_id}` | Resolve approved knowledge for recorded pet breed |

## Privacy and system

| Method | Endpoint | Capability |
|---|---|---|
| GET | `/privacy/export` | Authenticated customer data export |
| POST | `/privacy/requests` | Submit policy-gated privacy request |
| GET | `/system/policies` | Read active currency, delivery and payment-mode policies |
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | Dependency readiness |
| GET | `/internal/metrics` | Protected low-cardinality Prometheus metrics; excluded from OpenAPI |

## Single-operator operations

### Catalog, sourcing, fulfillment and trust

| Method | Endpoint | Capability |
|---|---|---|
| POST | `/operator/suppliers` | Create private supplier record |
| POST | `/operator/suppliers/{supplier_id}/assurances` | Record supplier authenticity assurance |
| POST | `/operator/products` | Create catalog product |
| POST | `/operator/offers` | Create sellable offer and shelf-life promise |
| PUT | `/operator/offers/{offer_id}/capacity` | Update enforceable capacity |
| POST | `/operator/offers/{offer_id}/reference-evidence` | Attach reference-price evidence/review date |
| POST | `/operator/order-lines/{line_id}/confirm-sourced` | Confirm sourced unit and exact expiry |
| POST | `/operator/orders/{order_id}/fulfillment` | Apply approved fulfillment transition |
| POST | `/operator/orders/{order_id}/deliver` | Mark delivered and create household inventory |
| POST | `/operator/orders/{order_id}/resolutions` | Propose policy-gated resolution |
| POST | `/operator/orders/{order_id}/late-credit` | Issue audited late credit |
| POST | `/operator/payments/{attempt_id}/reconcile` | Reconcile uncertain payment state |

### Journey and notification administration

| Method | Endpoint | Capability |
|---|---|---|
| POST | `/operator/journey-definitions` | Create draft finite journey definition |
| POST | `/operator/journey-definitions/{definition_id}/approve` | Approve professionally governed journey |
| POST | `/operator/notification-templates` | Create governed notification template |

### Knowledge import, review and activation

| Method | Endpoint | Capability |
|---|---|---|
| POST | `/operator/knowledge-releases/validate` | Dry-run validate collector package |
| POST | `/operator/knowledge-releases/import` | Import immutable release snapshot |
| GET | `/operator/knowledge-releases` | List imported release lifecycle |
| POST | `/operator/knowledge-claims/{claim_id}/review` | Record exact-claim veterinary decision |
| POST | `/operator/knowledge-claims/{claim_id}/withdraw` | Withdraw unsafe/outdated claim |
| POST | `/operator/knowledge-claims/{claim_id}/benchmark` | Register approved benchmark definition |
| POST | `/operator/knowledge-releases/{release_id}/guidance/import` | Import independently reviewed guidance |
| POST | `/operator/knowledge-releases/{release_id}/batch-approve` | Record certified anonymous batch decision |
| POST | `/operator/knowledge-releases/{release_id}/materialize-benchmarks` | Materialize approved structured ranges |
| POST | `/operator/knowledge-releases/{release_id}/publish` | Publish approved current release |
| POST | `/operator/knowledge-releases/{release_id}/withdraw` | Withdraw release from public use |
| GET | `/operator/knowledge-releases/{release_id}/reconciliation` | Compare stored and approved counts |
| GET | `/operator/knowledge-review-tasks` | List due/overdue re-review work |
| POST | `/operator/knowledge-activation-runs` | Create coordinated activation run |
| GET | `/operator/knowledge-activation-runs/{run_id}` | Inspect activation run and stages |
| POST | `/operator/knowledge-activation-runs/{run_id}/preflight` | Refresh blocked preflight |
| POST | `/operator/knowledge-activation-runs/{run_id}/execute` | Execute approval/publication transaction |
| POST | `/operator/knowledge-activation-runs/{run_id}/rollback` | Restore eligible prior release |

### Evidence, privacy and platform control

| Method | Endpoint | Capability |
|---|---|---|
| POST | `/operator/evidence-files` | Upload protected operational/review evidence |
| GET | `/operator/evidence-files/{evidence_id}` | Download protected evidence |
| POST | `/operator/body-assessments/{assessment_id}/confirm` | Record evidenced professional confirmation |
| GET | `/operator/customers/{identity_id}/overview` | 360-degree customer/household overview |
| GET | `/operator/privacy/requests` | List privacy operations backlog |
| POST | `/operator/privacy/requests/{request_id}/disable` | Disable identity and revoke sessions |
| GET | `/operator/webhooks/failed` | Inspect failed verified provider events |
| POST | `/operator/webhooks/{event_id}/replay` | Audited webhook replay |
| GET | `/operator/telemetry` | Operational backlog counters |
| GET | `/operator/audit/export` | Capped UTF-8 audit export |

