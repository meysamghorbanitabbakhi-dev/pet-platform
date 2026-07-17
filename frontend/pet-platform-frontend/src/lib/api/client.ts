"use client";

import type {
  AddressResponse,
  AddressBody,
  AvailabilitySubscriptionPage,
  AvailabilitySubscriptionResponse,
  CheckoutBody,
  CustomerRequestBody,
  CustomerRequestPage,
  CustomerRequestResponse,
  DiaryEntryDetailResponse,
  DiaryListItem,
  FoodEstimateResponse,
  GardenPlacementBody,
  GardenStateResponse,
  HouseholdBody,
  IdResponse,
  InventoryDetailResponse,
  InventoryListItem,
  JourneyCheckInBody,
  JourneyCheckInResponse,
  JourneyCompleteBody,
  JourneyCompletionResponse,
  JourneyDefinitionResponse,
  JourneyDetailResponse,
  JourneyOfferResponse,
  JourneyStartBody,
  JourneyStopBody,
  MeContextResponse,
  NotificationPage,
  OfferDetailResponse,
  OpenInventoryBody,
  OrderDetailResponse,
  OrderJourneyResponse,
  OrderPetPlanBody,
  OrderResponse,
  OtpRequestBody,
  OtpRequestResponse,
  OtpVerifyBody,
  OtpVerifyResponse,
  PaymentCallbackResponse,
  PaymentRedirectResponse,
  PaymentRequestBody,
  PetBody,
  PetProfilePatch,
  PetSummary,
  PolicyResponse,
  PrivacyRequestBody,
  PrivacyRequestResponse,
  ReorderAssessmentResponse,
  ReorderSnoozeBody,
  TodayResponse,
  WalletSummaryResponse,
} from "@/lib/api-types";
import { csrfHeaders } from "@/lib/session";
import { mapApiError } from "./errors";

export type PublicOtpVerifyResponse = Omit<
  OtpVerifyResponse,
  "access_token" | "refresh_token" | "token_type"
>;

async function parseError(response: Response) {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

async function bff<T>(
  path: string,
  init: Omit<RequestInit, "body"> & { body?: unknown } = {},
): Promise<T> {
  const mutation = init.method && init.method !== "GET";
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(mutation ? csrfHeaders() : {}),
      ...init.headers,
    },
    body: init.body ? JSON.stringify(init.body) : undefined,
  });
  if (!response.ok) {
    throw mapApiError(response.status, await parseError(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function requestOtp(body: OtpRequestBody) {
  return bff<OtpRequestResponse>("/api/bff/auth/otp/request", {
    method: "POST",
    body,
  });
}

export function verifyOtp(body: OtpVerifyBody) {
  return bff<PublicOtpVerifyResponse>("/api/bff/auth/otp/verify", {
    method: "POST",
    body,
  });
}

export function logout() {
  return bff<void>("/api/bff/auth/logout", { method: "POST" });
}

export function getPolicies() {
  return bff<PolicyResponse>("/api/bff/policies");
}

export function getMeContext() {
  return bff<MeContextResponse>("/api/bff/me/context");
}

export function createHousehold(body: HouseholdBody) {
  return bff<IdResponse>("/api/bff/households", { method: "POST", body });
}

export function createPet(householdId: string, body: PetBody) {
  return bff<IdResponse>(`/api/bff/households/${householdId}/pets`, {
    method: "POST",
    body,
  });
}

export function updatePetProfile(petId: string, body: PetProfilePatch) {
  return bff<Record<string, unknown>>(`/api/bff/pets/${petId}/profile`, {
    method: "PATCH",
    body,
  });
}

export function createAddress(householdId: string, body: AddressBody) {
  return bff<IdResponse>(`/api/bff/households/${householdId}/addresses`, {
    method: "POST",
    body,
  });
}

export function listAddresses(householdId: string) {
  return bff<AddressResponse[]>(`/api/bff/households/${householdId}/addresses`);
}

export function listHouseholdPets(householdId: string) {
  return bff<PetSummary[]>(`/api/bff/households/${householdId}/pets`);
}

export function getToday(petId: string) {
  return bff<TodayResponse>(`/api/bff/pets/${petId}/today`);
}

export function getJourneyOffers(petId: string) {
  return bff<JourneyOfferResponse[]>(`/api/bff/pets/${petId}/journey-offers`);
}

export function getInventoryDetail(unitId: string) {
  return bff<InventoryDetailResponse>(`/api/bff/inventory/${unitId}`);
}

export function openInventory(unitId: string, body: OpenInventoryBody) {
  return bff<FoodEstimateResponse>(`/api/bff/inventory/${unitId}/open`, {
    method: "POST",
    body,
  });
}

export function listHouseholdInventory(householdId: string) {
  return bff<InventoryListItem[]>(
    `/api/bff/households/${householdId}/inventory`,
  );
}

export function correctEstimate(unitId: string, body: OpenInventoryBody) {
  return bff<FoodEstimateResponse>(
    `/api/bff/inventory/${unitId}/estimate/correct`,
    { method: "POST", body },
  );
}

export function exhaustInventory(unitId: string) {
  return bff<void>(`/api/bff/inventory/${unitId}/exhaust`, { method: "POST" });
}

export function assessReorder(unitId: string) {
  return bff<ReorderAssessmentResponse>(
    `/api/bff/inventory/${unitId}/reorder-assessment`,
    { method: "POST" },
  );
}

export function snoozeReorder(unitId: string, body: ReorderSnoozeBody) {
  return bff<void>(`/api/bff/inventory/${unitId}/reorder-snooze`, {
    method: "PUT",
    body,
  });
}

export function listDiary(petId: string) {
  return bff<DiaryListItem[]>(`/api/bff/pets/${petId}/diary`);
}

export function getDiaryEntry(petId: string, entryId: string) {
  return bff<DiaryEntryDetailResponse>(
    `/api/bff/pets/${petId}/diary/${entryId}`,
  );
}

export function getGarden(petId: string) {
  return bff<GardenStateResponse>(`/api/bff/pets/${petId}/garden`);
}

export function placeGardenObject(rewardId: string, body: GardenPlacementBody) {
  return bff<void>(`/api/bff/garden/${rewardId}/placement`, {
    method: "PUT",
    body,
  });
}

export function returnGardenObject(rewardId: string) {
  return bff<void>(`/api/bff/garden/${rewardId}/placement`, {
    method: "DELETE",
  });
}

export function subscribeAvailability(offerId: string) {
  return bff<AvailabilitySubscriptionResponse>(
    `/api/bff/catalog/offers/${offerId}/availability-subscriptions`,
    { method: "POST" },
  );
}

export function cancelAvailabilitySubscription(offerId: string) {
  return bff<AvailabilitySubscriptionResponse>(
    `/api/bff/catalog/offers/${offerId}/availability-subscriptions`,
    { method: "DELETE" },
  );
}

export function listAvailabilitySubscriptions() {
  return bff<AvailabilitySubscriptionPage>("/api/bff/me/availability-subscriptions");
}

export function createCustomerRequest(
  body: CustomerRequestBody,
  idempotencyKey: string,
) {
  return bff<CustomerRequestResponse>("/api/bff/customer-requests", {
    method: "POST",
    body: { body, idempotencyKey },
  });
}

export function listCustomerRequests() {
  return bff<CustomerRequestPage>("/api/bff/customer-requests");
}

export function getCustomerRequest(requestId: string) {
  return bff<CustomerRequestResponse>(`/api/bff/customer-requests/${requestId}`);
}

export function getWallet(householdId: string) {
  return bff<WalletSummaryResponse>(`/api/bff/households/${householdId}/wallet`);
}

export function listNotifications() {
  return bff<NotificationPage>("/api/bff/notifications");
}

export function markNotificationRead(notificationId: string) {
  return bff<void>(`/api/bff/notifications/${notificationId}/read`, {
    method: "POST",
  });
}

export function requestPrivacyAction(body: PrivacyRequestBody) {
  return bff<PrivacyRequestResponse>("/api/bff/privacy/requests", {
    method: "POST",
    body,
  });
}

export function exportMyData() {
  return bff<Record<string, unknown>>("/api/bff/privacy/export");
}

export function getJourneyDefinition(definitionId: string) {
  return bff<JourneyDefinitionResponse>(
    `/api/bff/journey-definitions/${definitionId}`,
  );
}

export function startJourney(petId: string, body: JourneyStartBody) {
  return bff<IdResponse>(`/api/bff/pets/${petId}/journeys`, {
    method: "POST",
    body,
  });
}

export function getJourney(journeyId: string) {
  return bff<JourneyDetailResponse>(`/api/bff/journeys/${journeyId}`);
}

export function submitCheckIn(
  journeyId: string,
  body: JourneyCheckInBody,
  idempotencyKey: string,
) {
  return bff<JourneyCheckInResponse>(
    `/api/bff/journeys/${journeyId}/check-ins`,
    { method: "POST", body: { body, idempotencyKey } },
  );
}

export function pauseJourney(journeyId: string) {
  return bff<void>(`/api/bff/journeys/${journeyId}/pause`, { method: "POST" });
}

export function resumeJourney(journeyId: string) {
  return bff<void>(`/api/bff/journeys/${journeyId}/resume`, {
    method: "POST",
  });
}

export function stopJourney(journeyId: string, body: JourneyStopBody) {
  return bff<void>(`/api/bff/journeys/${journeyId}/stop`, {
    method: "POST",
    body,
  });
}

export function completeJourney(journeyId: string, body: JourneyCompleteBody) {
  return bff<JourneyCompletionResponse>(
    `/api/bff/journeys/${journeyId}/complete`,
    { method: "POST", body },
  );
}

export function getOfferDetail(offerId: string) {
  return bff<OfferDetailResponse>(`/api/bff/catalog/offers/${offerId}`);
}

export function createOrder(body: CheckoutBody, idempotencyKey: string) {
  return bff<OrderResponse>("/api/bff/checkout/orders", {
    method: "POST",
    body: { body, idempotencyKey },
  });
}

export function initiatePayment(
  orderId: string,
  body: PaymentRequestBody,
  idempotencyKey: string,
) {
  return bff<PaymentRedirectResponse>(
    `/api/bff/orders/${orderId}/payments/zarinpal`,
    {
      method: "POST",
      body: { body, idempotencyKey },
    },
  );
}

export function paymentCallback(authority: string, status: string | null) {
  const params = new URLSearchParams({ Authority: authority });
  if (status !== null) params.set("Status", status);
  return bff<PaymentCallbackResponse>(
    `/api/bff/payments/zarinpal/callback?${params.toString()}`,
  );
}

export function getOrderDetail(orderId: string) {
  return bff<OrderDetailResponse>(`/api/bff/orders/${orderId}`);
}

export function getOrderJourney(orderId: string) {
  return bff<OrderJourneyResponse>(`/api/bff/orders/${orderId}/journey`);
}

export function replaceOrderPetPlan(orderId: string, body: OrderPetPlanBody) {
  return bff<void>(`/api/bff/orders/${orderId}/pet-plan`, {
    method: "PUT",
    body,
  });
}
