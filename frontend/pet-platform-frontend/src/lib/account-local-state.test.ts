import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";
import { clearAccountLocalState } from "./account-local-state";
import { storeReturnTo } from "./auth-return";
import { addCartItem, readCart } from "./cart";
import { markOrderCreated, setLatestOrderId } from "./checkout-attempt";
import { writeCheckoutSelection } from "./checkout-selection";
import { mergeOnboardingProgress } from "./onboarding-progress";
import { selectedPetStorageKey } from "./selected-pet";

describe("clearAccountLocalState", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("clears every account-sensitive local storage key an active session can accumulate", () => {
    addCartItem("offer-1", 2);
    window.localStorage.setItem(selectedPetStorageKey, "pet-1");
    mergeOnboardingProgress({ householdId: "household-1" });
    writeCheckoutSelection({
      addressId: "address-1",
      householdId: "household-1",
    });
    markOrderCreated("signature-1", "order-1");
    setLatestOrderId("order-1");
    storeReturnTo("/today");

    expect(window.localStorage.length).toBeGreaterThan(0);

    clearAccountLocalState();

    // clearCart() empties the cart (and fires a change event reactive UI
    // depends on) rather than removing the key -- confirm it's empty, not
    // that the key is gone.
    expect(readCart().items).toEqual([]);
    expect(window.localStorage.getItem(selectedPetStorageKey)).toBeNull();
    expect(
      window.localStorage.getItem("pet-platform.onboarding-progress"),
    ).toBeNull();
    expect(
      window.localStorage.getItem("pet-platform.checkout-selection.v1"),
    ).toBeNull();
    expect(
      window.localStorage.getItem("pet-platform.checkout-attempt.v1"),
    ).toBeNull();
    expect(
      window.localStorage.getItem("pet-platform.latest-order-id"),
    ).toBeNull();
    expect(window.localStorage.getItem("pet-platform.auth-return")).toBeNull();
  });

  it("clears the React Query cache when a client is provided", () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(["me", "context"], { fake: "data" });
    expect(queryClient.getQueryData(["me", "context"])).toBeDefined();

    clearAccountLocalState(queryClient);

    expect(queryClient.getQueryData(["me", "context"])).toBeUndefined();
  });
});
