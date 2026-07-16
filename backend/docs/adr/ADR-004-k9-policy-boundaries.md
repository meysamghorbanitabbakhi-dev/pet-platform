# ADR-004: K9 policy configuration boundaries

**Status:** Accepted for K9.0 contract work

## Context

K9.0 exposes the policy values the frontend needs without authorizing new commercial or care-delivery behavior. K8 remains the runtime authority unless an explicit policy is enabled and its implementation exists.

## Decision

`Settings` and `GET /api/v1/system/policies` provide typed values for delivery commitment, canonical IRR/customer display metadata, late-credit handling, and future delivery-capability flags.

Defaults preserve the K8 launch posture:

- Currency is `IRR`; customer display unit metadata is `TOMAN` with `irr_per_customer_display_unit=10`. Monetary API values remain integer fields named `*_irr` and the backend does not round into toman.
- Delivery commitment remains 366 hours.
- Late-credit execution and customer visibility are disabled. Its amount and expiry configuration are retained for an approved future rollout.
- Reserve-now, cancellation after sourcing, self-service refund, replacement, substitution, and customer-visible delay compensation are disabled. Availability-subscription and concierge request capability metadata is enabled, but K9.0 exposes no workflow or order-creation endpoint for either capability.

The scheduler does not create late credits unless `late_credit_enabled` is true. Existing payment verification, sourcing, inventory, supplier privacy, and care-approval controls are unchanged.

## Policy decision register

The following are configuration boundaries only and require product, finance, operations, and/or care approval before behavior can be enabled:

| Unresolved decision | Current safe default | Affected endpoint/UI behavior | Approval would enable |
|---|---|---|---|
| Delivery commitment wording and exceptions | `delivery_commitment_hours=366`; factual timestamps only | `/system/policies`, order detail, order journey | Updated commitment copy and exception handling |
| Late-credit eligibility, rate, visibility and expiry | `late_credit_enabled=false`, `late_credit_customer_visible=false` | `/system/policies`, operator late-credit endpoint hidden from customer UX | Customer-visible credit issuance and wallet disclosure |
| Reserve-now workflow | `reserve_now_enabled=false`; no customer endpoint | Checkout and offer UI must not render reserve CTA | Approved reserve/payment/inventory flow |
| Cancellation after sourcing | `cancel_after_sourcing_enabled=false`; no customer self-service endpoint | Order UI must not expose self-service cancellation after sourcing | Approved cancellation workflow and disclosures |
| Self-service refund | `refund_self_service_enabled=false`; no customer endpoint | Support UI may submit request only; no refund promise | Approved refund request/decision flow |
| Self-service replacement | `replacement_self_service_enabled=false`; no customer endpoint | Support UI may submit request only; no replacement promise | Approved replacement request/decision flow |
| Self-service substitution | `substitution_self_service_enabled=false`; no customer endpoint | Catalog/order UI must not offer substitution | Approved substitution workflow |
| Delay compensation | `delay_compensation_customer_visible=false`; acknowledgement implies nothing | `/orders/{order_id}/delay-acknowledgements`, order delay UI | Explicit compensation policy and customer copy |
| Semantic remaining-level percentage bounds | CLOSED: `near_empty` 0–25%, `less_than_half` 25–50%, `more_than_half` 50–75%, `full` 75–100%; exact grams remain unknown | `/pet-life/inventory/{unit_id}/open`, `/estimate/correct` | Enabled MVP semantic opening from nominal quantity |
| Reorder safety buffer | CLOSED: `reorder_safety_buffer_days=3` | `/pet-life/inventory/{unit_id}/reorder-assessment`, Today reorder UX | Actionable reorder recommendation threshold |
| Early snooze break | CLOSED: break only when pessimistic remaining bound worsens by at least 2 days and now crosses reorder threshold | `/pet-life/inventory/{unit_id}/reorder-snooze`, Today attention | Re-surface reorder attention during active snooze only under approved worsening rule |
| Availability subscription notification copy and activation policy | In-app/SMS side effect only; `order_created=false`; max once per activation cycle | Availability subscription UI and notification inbox | Final customer wording, consent copy and activation-cycle operational rules |
| Concierge/support operating promises | Explicit promises all false | `/customer-requests`, customer support UI | Staffing/response-time/escalation commitments |
| Care journey delivery approval | `care_journey_delivery_enabled=false`; endpoints fail closed | Journey discovery, start, detail and check-in UI | Approved active journey content delivery |
| Push notifications | No push claim | Notification settings UI | Approved push channel and consent model |

Closed MVP policies remain documented here for traceability; only rows still marked as safe defaults without approval remain release blockers.

## Consequences

The frontend can feature-detect policy posture from a stable, named schema. Enabling a flag alone does not create a K9.1+ endpoint or workflow. Those changes require their own approved implementation and tests.
