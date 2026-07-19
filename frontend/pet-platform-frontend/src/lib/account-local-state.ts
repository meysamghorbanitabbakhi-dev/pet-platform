"use client";

import type { QueryClient } from "@tanstack/react-query";
import { clearCart } from "@/lib/cart";
import {
  clearCheckoutAttempt,
  clearLatestOrderId,
} from "@/lib/checkout-attempt";
import { clearCheckoutSelection } from "@/lib/checkout-selection";
import { clearOnboardingProgress } from "@/lib/onboarding-progress";
import { consumeReturnTo } from "@/lib/auth-return";
import { clearSelectedPetId } from "@/lib/selected-pet";

// Everything a logged-in browser session accumulates that is scoped to the
// account that was signed in -- must be wiped on logout or final session
// expiry so the next login (possibly a different account, possibly on a
// shared device) never sees a previous account's cart, selected pet,
// in-progress checkout, or cached query results.
export function clearAccountLocalState(queryClient?: QueryClient) {
  clearCart();
  clearSelectedPetId();
  clearOnboardingProgress();
  clearCheckoutSelection();
  clearCheckoutAttempt();
  clearLatestOrderId();
  consumeReturnTo(); // discards it: a stale return path must not survive a logout
  queryClient?.clear();
}
