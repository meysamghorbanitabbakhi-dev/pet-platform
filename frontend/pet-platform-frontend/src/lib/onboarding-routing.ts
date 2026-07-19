import type { MeContextResponse } from "@/lib/api-types";

export type OnboardingRoute =
  | "/auth/mobile"
  | "/onboarding/household"
  | "/onboarding/pet"
  | "/onboarding/address"
  | "/today";

export function routeFromMeContext(
  context: MeContextResponse,
): OnboardingRoute {
  if (context.onboarding.needs_household) return "/onboarding/household";
  if (context.onboarding.needs_pet) return "/onboarding/pet";
  if (context.onboarding.needs_address) return "/onboarding/address";
  return "/today";
}
