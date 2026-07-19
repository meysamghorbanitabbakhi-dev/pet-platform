import type { JourneyOfferResponse, PolicyResponse } from "@/lib/api-types";

const disabledByDefault = false;

export function isPolicyCompatible(policy: PolicyResponse): boolean {
  return (
    policy.currency_code === "IRR" &&
    policy.customer_display_currency_code === "IRR" &&
    policy.customer_display_unit === "TOMAN" &&
    policy.irr_per_customer_display_unit === 10 &&
    policy.delivery_commitment_hours === 366 &&
    policy.full_payment_only &&
    policy.sourcing_start_rule ===
      "supplier_financial_commitment_with_timestamp_and_evidence"
  );
}

export function enabled(
  policy: PolicyResponse | null | undefined,
  key: keyof PolicyResponse,
): boolean {
  const value = policy?.[key];
  return typeof value === "boolean" ? value : disabledByDefault;
}

export function shouldRenderReserveNow(
  policy: PolicyResponse | null | undefined,
): boolean {
  return enabled(policy, "reserve_now_enabled");
}

export function shouldRenderCareJourneys(
  policy: PolicyResponse | null | undefined,
  offers: JourneyOfferResponse[] | null | undefined,
): boolean {
  // The backend journey-offers endpoint only returns approved, active, species-eligible definitions.
  return (
    enabled(policy, "care_journey_delivery_enabled") && Boolean(offers?.length)
  );
}
