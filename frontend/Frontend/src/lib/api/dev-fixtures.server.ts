import "server-only";

import { cookies } from "next/headers";
import type {
  AddressBody,
  CheckoutBody,
  HouseholdBody,
  OpenInventoryBody,
  OrderPetPlanBody,
  OtpVerifyBody,
  PaymentRequestBody,
  PetBody,
  PetProfilePatch,
} from "@/lib/api-types";

const devOnboardingCookie = "pet_dev_onboarding";
const devTodayStateCookie = "pet_dev_today_state";

async function readDevStage() {
  return (await cookies()).get(devOnboardingCookie)?.value ?? "start";
}

async function writeDevStage(stage: "household" | "pet" | "complete") {
  (await cookies()).set(devOnboardingCookie, stage, {
    httpOnly: false,
    sameSite: "lax",
    path: "/",
  });
}

export async function loadDevelopmentApi() {
  if (
    process.env.NODE_ENV === "production" ||
    process.env.GATE_FIXTURE_MODE !== "1"
  ) {
    return null;
  }

  const fixtures = await import("@/test/fixtures/gate-fixtures");
  return {
    createAddress: async (_householdId: string, _body: AddressBody) => {
      void _householdId;
      void _body;
      await writeDevStage("complete");
      return { id: fixtures.ids.address };
    },
    createHousehold: async (_body: HouseholdBody) => {
      void _body;
      await writeDevStage("household");
      return { id: fixtures.ids.household };
    },
    createPet: async (_householdId: string, _body: PetBody) => {
      void _householdId;
      void _body;
      await writeDevStage("pet");
      return { id: fixtures.ids.petBishi };
    },
    getInventoryDetail: async (_unitId: string) => {
      void _unitId;
      return fixtures.inventoryDetailFixture;
    },
    getJourneyOffers: async (_petId: string) => {
      void _petId;
      return fixtures.journeyOffersFixture;
    },
    getMeContext: async () => {
      const stage = await readDevStage();
      if (stage === "complete") return fixtures.meContextFixture;
      if (stage === "pet") {
        return {
          ...fixtures.meContextFixture,
          onboarding: {
            needs_address: true,
            needs_household: false,
            needs_pet: false,
          },
          pets: [fixtures.meContextFixture.pets[0]],
        };
      }
      if (stage === "household") {
        return {
          ...fixtures.meContextFixture,
          onboarding: {
            needs_address: true,
            needs_household: false,
            needs_pet: true,
          },
          pets: [],
        };
      }
      return {
        ...fixtures.meContextFixture,
        default_household_id: null,
        households: [],
        onboarding: {
          needs_address: true,
          needs_household: true,
          needs_pet: true,
        },
        pets: [],
      };
    },
    getPolicies: async () => fixtures.policyFixture,
    getOfferDetail: async (offerId: string) => {
      if (offerId === fixtures.ids.offerCat)
        return fixtures.catOfferDetailFixture;
      if (offerId === fixtures.ids.offerUnavailable) {
        return fixtures.unavailableOfferFixture;
      }
      return fixtures.offerDetailFixture;
    },
    listAddresses: async (_householdId: string) => {
      void _householdId;
      const stage = await readDevStage();
      return stage === "complete" ? [fixtures.addressFixture] : [];
    },
    getToday: async (petId: string) =>
      (await cookies()).get(devTodayStateCookie)?.value === "unopened"
        ? fixtures.unopenedTodayFixture
        : petId === fixtures.ids.petRex
          ? fixtures.rexTodayFixture
          : fixtures.returningTodayFixture,
    listOffers: async () => fixtures.offersFixture,
    createOrder: async (_body: CheckoutBody, _idempotencyKey: string) => {
      void _body;
      void _idempotencyKey;
      return fixtures.orderResponseFixture;
    },
    initiatePayment: async (
      _orderId: string,
      _body: PaymentRequestBody,
      _idempotencyKey: string,
    ) => {
      void _orderId;
      void _body;
      void _idempotencyKey;
      return fixtures.paymentRedirectFixture;
    },
    paymentCallback: async (authority: string, status: string | null) => {
      if (authority === "fixture-authority" && status === "OK") {
        return fixtures.paymentCallbackFixture;
      }
      return {
        delivery_commitment_at: null,
        order_id: null,
        state: "cancelled_or_failed",
      };
    },
    getOrderDetail: async (_orderId: string) => {
      void _orderId;
      return fixtures.orderDetailFixture;
    },
    getOrderJourney: async (_orderId: string) => {
      void _orderId;
      return fixtures.orderJourneyFixture;
    },
    logout: async () => undefined,
    openInventory: async (_unitId: string, _body: OpenInventoryBody) => {
      void _unitId;
      void _body;
      return fixtures.openedEstimateFixture;
    },
    requestOtp: async (_body: unknown) => {
      void _body;
      return {
        challenge_id: fixtures.ids.journey,
        expires_in_seconds: 90,
      };
    },
    updatePetProfile: async (_petId: string, _body: PetProfilePatch) => {
      void _body;
      return { id: _petId };
    },
    replaceOrderPetPlan: async (_orderId: string, _body: OrderPetPlanBody) => {
      void _orderId;
      void _body;
      return undefined;
    },
    verifyOtp: async (body: OtpVerifyBody) => {
      if (body.code === "000000") {
        return {
          state: "invalid" as const,
          attempts_remaining: 2,
          expires_in_seconds: 60,
        };
      }
      if (body.code === "111111") {
        return {
          state: "expired" as const,
          attempts_remaining: 0,
          expires_in_seconds: 0,
        };
      }
      if (body.code === "222222") {
        return {
          state: "consumed" as const,
          attempts_remaining: 0,
          expires_in_seconds: 0,
        };
      }
      if (body.code === "333333") {
        return {
          state: "not_found" as const,
          attempts_remaining: 0,
          expires_in_seconds: 0,
        };
      }
      if (body.code === "999999") {
        return {
          state: "locked" as const,
          attempts_remaining: 0,
          expires_in_seconds: 900,
        };
      }
      return {
        access_token: "development-access-token-development-access-token",
        identity_id: "99999999-9999-4999-8999-999999999999",
        refresh_token: "development-refresh-token-development-refresh-token",
        state: "verified" as const,
        token_type: "bearer" as const,
      };
    },
  };
}
