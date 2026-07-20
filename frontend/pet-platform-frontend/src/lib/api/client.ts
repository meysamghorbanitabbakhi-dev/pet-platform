"use client";

import type {
  AddressResponse,
  AddressBody,
  AddressUpdateBody,
  AvailabilitySubscriptionPage,
  AvailabilitySubscriptionResponse,
  BodyAssessmentBody,
  BodyAssessmentItem,
  BreedDetailResponse,
  BreedListResponse,
  BreedSearchResponse,
  BreedSelectionBody,
  CareGuidanceResponse,
  CheckoutBody,
  ConciergeOfferAcceptBody,
  ConciergeOfferDeclineBody,
  ConciergeOfferResponse,
  ConsentBody,
  CustomerRequestBody,
  CustomerRequestPage,
  CustomerRequestResponse,
  DiaryEntryDetailResponse,
  DiaryListItem,
  FoodEstimateResponse,
  GardenPlacementBody,
  GardenStateResponse,
  GuidancePreferenceBody,
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
  MeasurementBody,
  MeasurementItem,
  MeContextResponse,
  NotificationPage,
  NotificationPreferenceBody,
  OfferDetailResponse,
  OfferSearchPage,
  OpenInventoryBody,
  DelayAcknowledgementResponse,
  OrderCancellationBody,
  OrderCancellationResponse,
  OrderDetailResponse,
  ShelfLifeExceptionResponse,
  OrderJourneyResponse,
  ProductAlternativeResponse,
  OrderListPage,
  OrderPetPlanBody,
  OrderResponse,
  OtpRequestBody,
  OtpRequestResponse,
  OtpVerifyBody,
  OtpVerifyResponse,
  PaymentCallbackResponse,
  PaymentRedirectResponse,
  PaymentRequestBody,
  PetAssetItem,
  PetBody,
  PetConsentResponse,
  PetKnowledgeResponse,
  PetProfilePatch,
  PetSummary,
  PolicyResponse,
  PrivacyRequestBody,
  PrivacyRequestPage,
  PrivacyRequestResponse,
  ReorderAssessmentResponse,
  ReorderSnoozeBody,
  ReplenishmentReservationApproveBody,
  ReplenishmentReservationDeclineBody,
  ReplenishmentReservationResponse,
  SmsPreferenceResponse,
  TodayResponse,
  WalletSummaryResponse,
  WeightTrendResponse,
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

export function updateAddress(
  householdId: string,
  addressId: string,
  body: AddressUpdateBody,
) {
  return bff<AddressResponse>(
    `/api/bff/households/${householdId}/addresses/${addressId}`,
    { method: "PATCH", body },
  );
}

export function deleteAddress(householdId: string, addressId: string) {
  return bff<void>(
    `/api/bff/households/${householdId}/addresses/${addressId}`,
    { method: "DELETE" },
  );
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

export function listReplenishmentReservations(householdId: string) {
  return bff<ReplenishmentReservationResponse[]>(
    `/api/bff/households/${householdId}/replenishment-reservations`,
  );
}

export function getReplenishmentReservation(reservationId: string) {
  return bff<ReplenishmentReservationResponse>(
    `/api/bff/replenishment-reservations/${reservationId}`,
  );
}

export function approveReplenishmentReservation(
  reservationId: string,
  body: ReplenishmentReservationApproveBody,
) {
  return bff<ReplenishmentReservationResponse>(
    `/api/bff/replenishment-reservations/${reservationId}/approve`,
    { method: "POST", body },
  );
}

export function declineReplenishmentReservation(
  reservationId: string,
  body: ReplenishmentReservationDeclineBody,
) {
  return bff<ReplenishmentReservationResponse>(
    `/api/bff/replenishment-reservations/${reservationId}/decline`,
    { method: "POST", body },
  );
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
  return bff<AvailabilitySubscriptionPage>(
    "/api/bff/me/availability-subscriptions",
  );
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
  return bff<CustomerRequestResponse>(
    `/api/bff/customer-requests/${requestId}`,
  );
}

export function listConciergeOffers(requestId: string) {
  return bff<ConciergeOfferResponse[]>(
    `/api/bff/customer-requests/${requestId}/concierge-offers`,
  );
}

export function acceptConciergeOffer(
  offerId: string,
  body: ConciergeOfferAcceptBody,
) {
  return bff<ConciergeOfferResponse>(
    `/api/bff/concierge-offers/${offerId}/accept`,
    { method: "POST", body },
  );
}

export function declineConciergeOffer(
  offerId: string,
  body: ConciergeOfferDeclineBody,
) {
  return bff<ConciergeOfferResponse>(
    `/api/bff/concierge-offers/${offerId}/decline`,
    { method: "POST", body },
  );
}

export function refreshConciergeOffer(offerId: string) {
  return bff<ConciergeOfferResponse>(
    `/api/bff/concierge-offers/${offerId}/refresh`,
    { method: "POST" },
  );
}

export function getWallet(householdId: string) {
  return bff<WalletSummaryResponse>(
    `/api/bff/households/${householdId}/wallet`,
  );
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

export function listPrivacyRequests() {
  return bff<PrivacyRequestPage>("/api/bff/privacy/requests");
}

export function getPrivacyRequest(requestId: string) {
  return bff<PrivacyRequestResponse>(`/api/bff/privacy/requests/${requestId}`);
}

export function getSmsPreference(eventKey: string) {
  return bff<SmsPreferenceResponse>(
    `/api/bff/notifications/preferences/${eventKey}/sms`,
  );
}

export function updateSmsPreference(
  eventKey: string,
  body: NotificationPreferenceBody,
) {
  return bff<void>(`/api/bff/notifications/preferences/${eventKey}/sms`, {
    method: "PUT",
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

export function searchOffers(q: string, limit = 25, offset = 0) {
  const params = new URLSearchParams({
    q,
    limit: String(limit),
    offset: String(offset),
  });
  return bff<OfferSearchPage>(`/api/bff/catalog/offers/search?${params}`);
}

export function listProductAlternatives(productId: string) {
  return bff<ProductAlternativeResponse[]>(
    `/api/bff/catalog/products/${productId}/alternatives`,
  );
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

export function listOrders() {
  return bff<OrderListPage>("/api/bff/orders");
}

export function acknowledgeOrderDelay(orderId: string, idempotencyKey: string) {
  return bff<DelayAcknowledgementResponse>(
    `/api/bff/orders/${orderId}/delay-acknowledgements`,
    { method: "POST", body: { idempotencyKey } },
  );
}

export function getOrderDetail(orderId: string) {
  return bff<OrderDetailResponse>(`/api/bff/orders/${orderId}`);
}

export function cancelOrder(orderId: string, body: OrderCancellationBody) {
  return bff<OrderCancellationResponse>(`/api/bff/orders/${orderId}/cancel`, {
    method: "POST",
    body,
  });
}

export function listShelfLifeExceptions(orderId: string) {
  return bff<ShelfLifeExceptionResponse[]>(
    `/api/bff/orders/${orderId}/shelf-life-exceptions`,
  );
}

export function acceptShelfLifeException(orderId: string, exceptionId: string) {
  return bff<ShelfLifeExceptionResponse>(
    `/api/bff/orders/${orderId}/shelf-life-exceptions/${exceptionId}/accept`,
    { method: "POST" },
  );
}

export function declineShelfLifeException(
  orderId: string,
  exceptionId: string,
) {
  return bff<ShelfLifeExceptionResponse>(
    `/api/bff/orders/${orderId}/shelf-life-exceptions/${exceptionId}/decline`,
    { method: "POST" },
  );
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

export function listMeasurements(petId: string) {
  return bff<MeasurementItem[]>(`/api/bff/pets/${petId}/measurements`);
}

export function recordMeasurement(petId: string, body: MeasurementBody) {
  return bff<{ id: string; status: string }>(
    `/api/bff/pets/${petId}/measurements`,
    { method: "POST", body },
  );
}

export function getWeightTrend(petId: string) {
  return bff<WeightTrendResponse>(`/api/bff/pets/${petId}/weight-trend`);
}

export function listPetAssets(petId: string) {
  return bff<PetAssetItem[]>(`/api/bff/pets/${petId}/assets`);
}

export function listPetConsents(petId: string) {
  return bff<PetConsentResponse[]>(`/api/bff/pets/${petId}/consents`);
}

export function grantPetConsent(petId: string, body: ConsentBody) {
  return bff<PetConsentResponse>(`/api/bff/pets/${petId}/consents`, {
    method: "POST",
    body,
  });
}

export function withdrawPetConsent(petId: string, consentId: string) {
  return bff<void>(`/api/bff/pets/${petId}/consents/${consentId}/withdraw`, {
    method: "POST",
  });
}

export async function uploadPetAsset(
  petId: string,
  file: File,
  options: { category: string; consentId: string },
): Promise<{ id: string; status: string }> {
  const response = await fetch(`/api/bff/pets/${petId}/assets`, {
    body: file,
    credentials: "include",
    headers: {
      "Content-Type": file.type,
      "X-Asset-Category": options.category,
      "X-Consent-ID": options.consentId,
      "X-Filename": file.name,
      ...csrfHeaders(),
    },
    method: "POST",
  });
  if (!response.ok) {
    throw mapApiError(
      response.status,
      await response.json().catch(() => undefined),
    );
  }
  return response.json();
}

export function petAssetUrl(petId: string, assetId: string) {
  return `/api/bff/pets/${petId}/assets/${assetId}`;
}

export function deletePetAsset(petId: string, assetId: string) {
  return bff<void>(`/api/bff/pets/${petId}/assets/${assetId}`, {
    method: "DELETE",
  });
}

export function createBodyAssessment(petId: string, body: BodyAssessmentBody) {
  return bff<{ id: string; assessment_source: string }>(
    `/api/bff/pets/${petId}/body-assessments`,
    { method: "POST", body },
  );
}

export function listBodyAssessments(petId: string) {
  return bff<BodyAssessmentItem[]>(`/api/bff/pets/${petId}/body-assessments`);
}

export function listBreeds(species?: "dog" | "cat") {
  const query = species ? `?species=${species}` : "";
  return bff<BreedListResponse>(`/api/bff/breeds${query}`);
}

export function searchBreeds(query: string, species?: "dog" | "cat") {
  const params = new URLSearchParams({ q: query });
  if (species) params.set("species", species);
  return bff<BreedSearchResponse>(`/api/bff/breeds/search?${params}`);
}

export function getBreedDetail(breedId: string) {
  return bff<BreedDetailResponse>(`/api/bff/breeds/${breedId}`);
}

export function getPetKnowledge(petId: string) {
  return bff<PetKnowledgeResponse>(`/api/bff/pets/${petId}/knowledge`);
}

export function selectPetBreed(petId: string, body: BreedSelectionBody) {
  return bff<void>(`/api/bff/pets/${petId}/breed-selection`, {
    method: "PUT",
    body,
  });
}

export function getPetCareGuidance(petId: string) {
  return bff<CareGuidanceResponse>(`/api/bff/pets/${petId}/care-guidance`);
}

export function setGuidancePreference(
  petId: string,
  guidanceId: string,
  body: GuidancePreferenceBody,
) {
  return bff<void>(
    `/api/bff/pets/${petId}/care-guidance/${guidanceId}/preference`,
    { method: "PUT", body },
  );
}
