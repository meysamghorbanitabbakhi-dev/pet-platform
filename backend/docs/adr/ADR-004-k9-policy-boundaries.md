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

## Policy decisions still blocked

The following are configuration boundaries only and require product, finance, operations, and/or care approval before behavior can be enabled:

| Item | Status | Required decision |
| --- | --- | --- |
| Delivery commitment and customer display wording | POLICY BLOCKED | Service-level commitment, locale wording, and exception handling |
| Late-credit enablement/visibility, rate, and expiry | POLICY BLOCKED | Eligibility, funding, disclosure, and expiry policy |
| Reserve-now and self-service resolutions | POLICY BLOCKED | Commercial workflow, inventory, payment, and support controls |
| Availability subscription and concierge | POLICY BLOCKED | Product scope, consent, operations, and support model |
| Care-journey delivery | POLICY BLOCKED | Clinical/content approval, eligibility, and delivery controls |
| Semantic remaining-level bounds | POLICY BLOCKED | Approved percentage bands for full/more-than-half/less-than-half/near-empty |
| Reorder safety buffer | POLICY BLOCKED | Approved pessimistic buffer before reorder recommendation becomes actionable |
| Early snooze break | POLICY BLOCKED | Material-worsening threshold that may end a snooze before expiry |

## Consequences

The frontend can feature-detect policy posture from a stable, named schema. Enabling a flag alone does not create a K9.1+ endpoint or workflow. Those changes require their own approved implementation and tests.
