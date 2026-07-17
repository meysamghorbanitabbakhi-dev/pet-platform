import type { components, paths } from "@/generated/openapi";

export type ApiPaths = paths;
export type Schema<Name extends keyof components["schemas"]> =
  components["schemas"][Name];

export type PolicyResponse = Schema<"PolicyResponse">;
export type OtpRequestBody = Schema<"OtpRequestBody">;
export type OtpRequestResponse = Schema<"OtpRequestResponse">;
export type OtpVerifyBody = Schema<"OtpVerifyBody">;
export type OtpVerifyResponse = Schema<"OtpVerifyResponse">;
export type MeContextResponse = Schema<"MeContextResponse">;
export type ContextPetSummary = Schema<"ContextPetSummary">;
export type OfferListItem = Schema<"OfferListItem">;
export type TodayResponse = Schema<"TodayResponse">;
export type TodayFood = TodayResponse["food"];
export type JourneyOfferResponse = Schema<"JourneyOfferResponse">;
export type InventoryDetailResponse = Schema<"InventoryDetailResponse">;
export type OpenInventoryBody = Schema<"OpenInventoryBody">;
export type FoodEstimateResponse = Schema<"FoodEstimateResponse">;
export type HouseholdBody = Schema<"HouseholdBody">;
export type PetBody = Schema<"PetBody">;
export type AddressBody = Schema<"AddressBody">;
export type IdResponse = Schema<"IdResponse">;
