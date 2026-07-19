import "server-only";

import createClient from "openapi-fetch";
import type {
  AddressResponse,
  AddressBody,
  AddressUpdateBody,
  ApiPaths,
  CheckoutBody,
  HouseholdBody,
  InventoryDetailResponse,
  JourneyOfferResponse,
  MeContextResponse,
  OfferDetailResponse,
  OfferListItem,
  OfferSearchPage,
  OpenInventoryBody,
  ProductAlternativeResponse,
  OrderDetailResponse,
  OrderJourneyResponse,
  OrderPetPlanBody,
  OrderResponse,
  OtpRequestBody,
  OtpRequestResponse,
  AvailabilitySubscriptionPage,
  AvailabilitySubscriptionResponse,
  CustomerRequestBody,
  CustomerRequestPage,
  CustomerRequestResponse,
  DelayAcknowledgementResponse,
  DiaryEntryDetailResponse,
  DiaryListItem,
  GardenPlacementBody,
  GardenStateResponse,
  InventoryListItem,
  JourneyCheckInBody,
  NotificationPage,
  NotificationPreferenceBody,
  OrderListPage,
  PrivacyRequestBody,
  PrivacyRequestPage,
  PrivacyRequestResponse,
  SmsPreferenceResponse,
  WalletSummaryResponse,
  JourneyCheckInResponse,
  JourneyCompleteBody,
  JourneyCompletionResponse,
  JourneyDefinitionResponse,
  JourneyDetailResponse,
  JourneyStartBody,
  JourneyStopBody,
  OtpVerifyBody,
  OtpVerifyResponse,
  PaymentCallbackResponse,
  PaymentRedirectResponse,
  PaymentRequestBody,
  PetBody,
  PetProfilePatch,
  PetSummary,
  PolicyResponse,
  ReorderAssessmentResponse,
  ReorderSnoozeBody,
  TodayResponse,
} from "@/lib/api-types";
import type {
  BodyAssessmentBody,
  BodyAssessmentItem,
  BodyAssessmentMutationResponse,
  BreedDetailResponse,
  BreedListResponse,
  BreedSearchResponse,
  BreedSelectionBody,
  CareGuidanceResponse,
  ConsentBody,
  GuidancePreferenceBody,
  MeasurementBody,
  MeasurementItem,
  MeasurementMutationResponse,
  PetAssetItem,
  PetAssetMutationResponse,
  PetConsentResponse,
  PetKnowledgeResponse,
  WeightTrendResponse,
} from "@/lib/api-types";
import {
  clearSessionCookies,
  readAccessToken,
  readRefreshToken,
  setSessionCookies,
} from "@/lib/session/server";
import { loadDevelopmentApi } from "./dev-fixtures.server";

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const backendClient = createClient<ApiPaths>({
  baseUrl,
  credentials: "omit",
});

type ApiResult<T> = {
  data?: T;
  error?: unknown;
  response: Response;
};

export class BackendApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: unknown,
  ) {
    super("Backend API request failed");
    this.name = "BackendApiError";
  }
}

function toAuthHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function unwrap<T>(result: ApiResult<T>): Promise<T> {
  if (result.error || !result.data) {
    throw new BackendApiError(result.response.status, result.error);
  }
  return result.data;
}

async function unwrapVoid(result: ApiResult<unknown>): Promise<void> {
  if (result.error || !result.response.ok) {
    throw new BackendApiError(result.response.status, result.error);
  }
}

async function refreshSessionOnce(): Promise<string | null> {
  const refreshToken = await readRefreshToken();
  if (!refreshToken) return null;

  const result = await backendClient.POST("/api/v1/auth/session/refresh", {
    body: { refresh_token: refreshToken },
  });
  if (result.error || !result.data) {
    await clearSessionCookies();
    return null;
  }
  await setSessionCookies(result.data);
  return result.data.access_token;
}

async function withAuth<T>(
  call: (headers: HeadersInit) => Promise<ApiResult<T>>,
): Promise<T> {
  const firstToken = await readAccessToken();
  let result = await call(toAuthHeaders(firstToken));
  if (result.response.status === 401) {
    const refreshedToken = await refreshSessionOnce();
    if (refreshedToken) {
      result = await call(toAuthHeaders(refreshedToken));
    }
  }
  if (result.response.status === 401) {
    await clearSessionCookies();
  }
  return unwrap(result);
}

async function withAuthVoid(
  call: (headers: HeadersInit) => Promise<ApiResult<unknown>>,
): Promise<void> {
  const firstToken = await readAccessToken();
  let result = await call(toAuthHeaders(firstToken));
  if (result.response.status === 401) {
    const refreshedToken = await refreshSessionOnce();
    if (refreshedToken) {
      result = await call(toAuthHeaders(refreshedToken));
    }
  }
  if (result.response.status === 401) {
    await clearSessionCookies();
  }
  return unwrapVoid(result);
}

// Raw-fetch path for binary payloads (pet asset upload/download) that openapi-fetch's
// JSON-oriented client cannot express: the backend takes/returns raw bytes with
// custom headers, not a JSON body.
async function withAuthRawFetch(
  call: (headers: HeadersInit) => Promise<Response>,
): Promise<Response> {
  const firstToken = await readAccessToken();
  let response = await call(toAuthHeaders(firstToken));
  if (response.status === 401) {
    const refreshedToken = await refreshSessionOnce();
    if (refreshedToken) {
      response = await call(toAuthHeaders(refreshedToken));
    }
  }
  if (response.status === 401) {
    await clearSessionCookies();
  }
  return response;
}

export async function requestOtpBackend(
  body: OtpRequestBody,
): Promise<OtpRequestResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.requestOtp(body);
  return unwrap(await backendClient.POST("/api/v1/auth/otp/request", { body }));
}

export async function verifyOtpBackend(
  body: OtpVerifyBody,
): Promise<OtpVerifyResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.verifyOtp(body);
  return unwrap(await backendClient.POST("/api/v1/auth/otp/verify", { body }));
}

export async function logoutBackend(): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) {
    await developmentApi.logout();
    await clearSessionCookies();
    return;
  }
  const refreshToken = await readRefreshToken();
  if (!refreshToken) {
    await clearSessionCookies();
    return;
  }
  await withAuthVoid((headers) =>
    backendClient.POST("/api/v1/auth/session/logout", {
      body: { refresh_token: refreshToken },
      headers,
    }),
  ).catch(async () => {
    await clearSessionCookies();
  });
  await clearSessionCookies();
}

export async function getPoliciesBackend(): Promise<PolicyResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getPolicies();
  return unwrap(await backendClient.GET("/api/v1/system/policies"));
}

export async function getMeContextBackend(): Promise<MeContextResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getMeContext();
  return withAuth((headers) =>
    backendClient.GET("/api/v1/me/context", { headers }),
  );
}

export async function createHouseholdBackend(body: HouseholdBody) {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.createHousehold(body);
  return withAuth((headers) =>
    backendClient.POST("/api/v1/pet-life/households", { body, headers }),
  );
}

export async function createPetBackend(householdId: string, body: PetBody) {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.createPet(householdId, body);
  return withAuth((headers) =>
    backendClient.POST("/api/v1/pet-life/households/{household_id}/pets", {
      params: { path: { household_id: householdId } },
      body,
      headers,
    }),
  );
}

export async function updatePetProfileBackend(
  petId: string,
  body: PetProfilePatch,
) {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.updatePetProfile(petId, body);
  return withAuth((headers) =>
    backendClient.PATCH("/api/v1/pet-life/pets/{pet_id}/profile", {
      params: { path: { pet_id: petId } },
      body,
      headers,
    }),
  );
}

export async function createAddressBackend(
  householdId: string,
  body: AddressBody,
) {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.createAddress(householdId, body);
  return withAuth((headers) =>
    backendClient.POST("/api/v1/pet-life/households/{household_id}/addresses", {
      params: { path: { household_id: householdId } },
      body,
      headers,
    }),
  );
}

export async function listHouseholdPetsBackend(
  householdId: string,
): Promise<PetSummary[]> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listHouseholdPets(householdId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/households/{household_id}/pets", {
      params: { path: { household_id: householdId } },
      headers,
    }),
  );
}

export async function listAddressesBackend(
  householdId: string,
): Promise<AddressResponse[]> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listAddresses(householdId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/households/{household_id}/addresses", {
      params: { path: { household_id: householdId } },
      headers,
    }),
  );
}

export async function updateAddressBackend(
  householdId: string,
  addressId: string,
  body: AddressUpdateBody,
): Promise<AddressResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi)
    return developmentApi.updateAddress(householdId, addressId, body);
  return withAuth((headers) =>
    backendClient.PATCH(
      "/api/v1/pet-life/households/{household_id}/addresses/{address_id}",
      {
        params: { path: { household_id: householdId, address_id: addressId } },
        body,
        headers,
      },
    ),
  );
}

export async function deleteAddressBackend(
  householdId: string,
  addressId: string,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi)
    return developmentApi.deleteAddress(householdId, addressId);
  return withAuthVoid((headers) =>
    backendClient.DELETE(
      "/api/v1/pet-life/households/{household_id}/addresses/{address_id}",
      {
        params: { path: { household_id: householdId, address_id: addressId } },
        headers,
      },
    ),
  );
}

export async function getTodayBackend(petId: string): Promise<TodayResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getToday(petId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/pets/{pet_id}/today", {
      params: { path: { pet_id: petId } },
      headers,
    }),
  );
}

export async function getJourneyOffersBackend(
  petId: string,
): Promise<JourneyOfferResponse[]> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getJourneyOffers(petId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/pets/{pet_id}/journey-offers", {
      params: { path: { pet_id: petId } },
      headers,
    }),
  );
}

export async function listHouseholdInventoryBackend(
  householdId: string,
): Promise<InventoryListItem[]> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listHouseholdInventory(householdId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/households/{household_id}/inventory", {
      params: { path: { household_id: householdId } },
      headers,
    }),
  );
}

export async function correctEstimateBackend(
  unitId: string,
  body: OpenInventoryBody,
) {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.correctEstimate(unitId, body);
  return withAuth((headers) =>
    backendClient.POST(
      "/api/v1/pet-life/inventory/{unit_id}/estimate/correct",
      {
        params: { path: { unit_id: unitId } },
        body,
        headers,
      },
    ),
  );
}

export async function exhaustInventoryBackend(unitId: string): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.exhaustInventory(unitId);
  return withAuthVoid((headers) =>
    backendClient.POST("/api/v1/pet-life/inventory/{unit_id}/exhaust", {
      params: { path: { unit_id: unitId } },
      headers,
    }),
  );
}

export async function assessReorderBackend(
  unitId: string,
): Promise<ReorderAssessmentResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.assessReorder(unitId);
  return withAuth((headers) =>
    backendClient.POST(
      "/api/v1/pet-life/inventory/{unit_id}/reorder-assessment",
      {
        params: { path: { unit_id: unitId } },
        headers,
      },
    ),
  );
}

export async function snoozeReorderBackend(
  unitId: string,
  body: ReorderSnoozeBody,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.snoozeReorder(unitId, body);
  return withAuthVoid((headers) =>
    backendClient.PUT("/api/v1/pet-life/inventory/{unit_id}/reorder-snooze", {
      params: { path: { unit_id: unitId } },
      body,
      headers,
    }),
  );
}

export async function getJourneyDefinitionBackend(
  definitionId: string,
): Promise<JourneyDefinitionResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getJourneyDefinition(definitionId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/journey-definitions/{definition_id}", {
      params: { path: { definition_id: definitionId } },
      headers,
    }),
  );
}

export async function startJourneyBackend(
  petId: string,
  body: JourneyStartBody,
) {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.startJourney(petId, body);
  return withAuth((headers) =>
    backendClient.POST("/api/v1/pet-life/pets/{pet_id}/journeys", {
      params: { path: { pet_id: petId } },
      body,
      headers,
    }),
  );
}

export async function getJourneyBackend(
  journeyId: string,
): Promise<JourneyDetailResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getJourney(journeyId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/journeys/{journey_id}", {
      params: { path: { journey_id: journeyId } },
      headers,
    }),
  );
}

export async function submitCheckInBackend(
  journeyId: string,
  body: JourneyCheckInBody,
  idempotencyKey: string,
): Promise<JourneyCheckInResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) {
    return developmentApi.submitCheckIn(journeyId, body, idempotencyKey);
  }
  return withAuth((headers) =>
    backendClient.POST("/api/v1/pet-life/journeys/{journey_id}/check-ins", {
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { journey_id: journeyId },
      },
      body,
      headers,
    }),
  );
}

export async function pauseJourneyBackend(journeyId: string): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.pauseJourney(journeyId);
  return withAuthVoid((headers) =>
    backendClient.POST("/api/v1/pet-life/journeys/{journey_id}/pause", {
      params: { path: { journey_id: journeyId } },
      headers,
    }),
  );
}

export async function resumeJourneyBackend(journeyId: string): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.resumeJourney(journeyId);
  return withAuthVoid((headers) =>
    backendClient.POST("/api/v1/pet-life/journeys/{journey_id}/resume", {
      params: { path: { journey_id: journeyId } },
      headers,
    }),
  );
}

export async function stopJourneyBackend(
  journeyId: string,
  body: JourneyStopBody,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.stopJourney(journeyId, body);
  return withAuthVoid((headers) =>
    backendClient.POST("/api/v1/pet-life/journeys/{journey_id}/stop", {
      params: { path: { journey_id: journeyId } },
      body,
      headers,
    }),
  );
}

export async function completeJourneyBackend(
  journeyId: string,
  body: JourneyCompleteBody,
): Promise<JourneyCompletionResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.completeJourney(journeyId, body);
  return withAuth((headers) =>
    backendClient.POST("/api/v1/pet-life/journeys/{journey_id}/complete", {
      params: { path: { journey_id: journeyId } },
      body,
      headers,
    }),
  );
}

export async function listDiaryBackend(
  petId: string,
): Promise<DiaryListItem[]> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listDiary(petId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/pets/{pet_id}/diary", {
      params: { path: { pet_id: petId } },
      headers,
    }),
  );
}

export async function getDiaryEntryBackend(
  petId: string,
  entryId: string,
): Promise<DiaryEntryDetailResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getDiaryEntry(petId, entryId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/pets/{pet_id}/diary/{entry_id}", {
      params: { path: { entry_id: entryId, pet_id: petId } },
      headers,
    }),
  );
}

export async function getGardenBackend(
  petId: string,
): Promise<GardenStateResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getGarden(petId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/pets/{pet_id}/garden", {
      params: { path: { pet_id: petId } },
      headers,
    }),
  );
}

export async function placeGardenObjectBackend(
  rewardId: string,
  body: GardenPlacementBody,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.placeGardenObject(rewardId, body);
  return withAuthVoid((headers) =>
    backendClient.PUT("/api/v1/pet-life/garden/{reward_id}/placement", {
      params: { path: { reward_id: rewardId } },
      body,
      headers,
    }),
  );
}

export async function returnGardenObjectBackend(
  rewardId: string,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.returnGardenObject(rewardId);
  return withAuthVoid((headers) =>
    backendClient.DELETE("/api/v1/pet-life/garden/{reward_id}/placement", {
      params: { path: { reward_id: rewardId } },
      headers,
    }),
  );
}

export async function subscribeAvailabilityBackend(
  offerId: string,
): Promise<AvailabilitySubscriptionResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.subscribeAvailability(offerId);
  return withAuth((headers) =>
    backendClient.POST(
      "/api/v1/catalog/offers/{offer_id}/availability-subscriptions",
      { params: { path: { offer_id: offerId } }, headers },
    ),
  );
}

export async function cancelAvailabilitySubscriptionBackend(
  offerId: string,
): Promise<AvailabilitySubscriptionResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) {
    return developmentApi.cancelAvailabilitySubscription(offerId);
  }
  return withAuth((headers) =>
    backendClient.DELETE(
      "/api/v1/catalog/offers/{offer_id}/availability-subscriptions",
      { params: { path: { offer_id: offerId } }, headers },
    ),
  );
}

export async function listAvailabilitySubscriptionsBackend(): Promise<AvailabilitySubscriptionPage> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listAvailabilitySubscriptions();
  return withAuth((headers) =>
    backendClient.GET("/api/v1/me/availability-subscriptions", { headers }),
  );
}

export async function createCustomerRequestBackend(
  body: CustomerRequestBody,
  idempotencyKey: string,
): Promise<CustomerRequestResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) {
    return developmentApi.createCustomerRequest(body, idempotencyKey);
  }
  return withAuth((headers) =>
    backendClient.POST("/api/v1/customer-requests", {
      body,
      headers,
      params: { header: { "Idempotency-Key": idempotencyKey } },
    }),
  );
}

export async function listCustomerRequestsBackend(): Promise<CustomerRequestPage> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listCustomerRequests();
  return withAuth((headers) =>
    backendClient.GET("/api/v1/customer-requests", { headers }),
  );
}

export async function getCustomerRequestBackend(
  requestId: string,
): Promise<CustomerRequestResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getCustomerRequest(requestId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/customer-requests/{request_id}", {
      params: { path: { request_id: requestId } },
      headers,
    }),
  );
}

export async function getWalletBackend(
  householdId: string,
): Promise<WalletSummaryResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getWallet(householdId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/households/{household_id}/wallet", {
      params: { path: { household_id: householdId } },
      headers,
    }),
  );
}

export async function listNotificationsBackend(): Promise<NotificationPage> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listNotifications();
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/notifications", { headers }),
  );
}

export async function markNotificationReadBackend(
  notificationId: string,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi)
    return developmentApi.markNotificationRead(notificationId);
  return withAuthVoid((headers) =>
    backendClient.POST(
      "/api/v1/pet-life/notifications/{notification_id}/read",
      {
        params: { path: { notification_id: notificationId } },
        headers,
      },
    ),
  );
}

export async function getSmsPreferenceBackend(
  eventKey: string,
): Promise<SmsPreferenceResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getSmsPreference(eventKey);
  return withAuth((headers) =>
    backendClient.GET(
      "/api/v1/pet-life/notifications/preferences/{event_key}/sms",
      {
        params: { path: { event_key: eventKey } },
        headers,
      },
    ),
  );
}

export async function updateSmsPreferenceBackend(
  eventKey: string,
  body: NotificationPreferenceBody,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.updateSmsPreference(eventKey, body);
  return withAuthVoid((headers) =>
    backendClient.PUT(
      "/api/v1/pet-life/notifications/preferences/{event_key}/sms",
      {
        params: { path: { event_key: eventKey } },
        body,
        headers,
      },
    ),
  );
}

export async function requestPrivacyActionBackend(
  body: PrivacyRequestBody,
): Promise<PrivacyRequestResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.requestPrivacyAction(body);
  return withAuth((headers) =>
    backendClient.POST("/api/v1/privacy/requests", { body, headers }),
  );
}

export async function listPrivacyRequestsBackend(): Promise<PrivacyRequestPage> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listPrivacyRequests();
  return withAuth((headers) =>
    backendClient.GET("/api/v1/privacy/requests", { headers }),
  );
}

export async function getPrivacyRequestBackend(
  requestId: string,
): Promise<PrivacyRequestResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getPrivacyRequest(requestId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/privacy/requests/{request_id}", {
      params: { path: { request_id: requestId } },
      headers,
    }),
  );
}

export async function exportMyDataBackend(): Promise<Record<string, unknown>> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.exportMyData();
  return withAuth((headers) =>
    backendClient.GET("/api/v1/privacy/export", { headers }),
  );
}

export async function listMeasurementsBackend(
  petId: string,
): Promise<MeasurementItem[]> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listMeasurements(petId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/pets/{pet_id}/measurements", {
      params: { path: { pet_id: petId } },
      headers,
    }),
  );
}

export async function recordMeasurementBackend(
  petId: string,
  body: MeasurementBody,
): Promise<MeasurementMutationResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.recordMeasurement(petId, body);
  return withAuth((headers) =>
    backendClient.POST("/api/v1/pet-life/pets/{pet_id}/measurements", {
      params: { path: { pet_id: petId } },
      body,
      headers,
    }),
  );
}

export async function getWeightTrendBackend(
  petId: string,
): Promise<WeightTrendResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getWeightTrend(petId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/pets/{pet_id}/weight-trend", {
      params: { path: { pet_id: petId } },
      headers,
    }),
  );
}

export async function listPetAssetsBackend(
  petId: string,
): Promise<PetAssetItem[]> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listPetAssets(petId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/pets/{pet_id}/assets", {
      params: { path: { pet_id: petId } },
      headers,
    }),
  );
}

export async function listPetConsentsBackend(
  petId: string,
): Promise<PetConsentResponse[]> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listPetConsents(petId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/pets/{pet_id}/consents", {
      params: { path: { pet_id: petId } },
      headers,
    }),
  );
}

export async function grantPetConsentBackend(
  petId: string,
  body: ConsentBody,
): Promise<PetConsentResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.grantPetConsent(petId, body);
  return withAuth((headers) =>
    backendClient.POST("/api/v1/pet-life/pets/{pet_id}/consents", {
      params: { path: { pet_id: petId } },
      body,
      headers,
    }),
  );
}

export async function withdrawPetConsentBackend(
  petId: string,
  consentId: string,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi)
    return developmentApi.withdrawPetConsent(petId, consentId);
  await withAuthVoid((headers) =>
    backendClient.POST(
      "/api/v1/pet-life/pets/{pet_id}/consents/{consent_id}/withdraw",
      {
        params: { path: { pet_id: petId, consent_id: consentId } },
        headers,
      },
    ),
  );
}

export async function uploadPetAssetBackend(
  petId: string,
  file: { bytes: ArrayBuffer; mediaType: string },
  headers: { filename: string; category: string; consentId: string },
): Promise<PetAssetMutationResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) {
    return developmentApi.uploadPetAsset(petId, headers);
  }
  const response = await withAuthRawFetch((authHeaders) =>
    fetch(`${baseUrl}/api/v1/pet-life/pets/${petId}/assets`, {
      body: file.bytes,
      headers: {
        ...authHeaders,
        "Content-Type": file.mediaType,
        "X-Asset-Category": headers.category,
        "X-Consent-ID": headers.consentId,
        "X-Filename": headers.filename,
      },
      method: "POST",
    }),
  );
  if (!response.ok) {
    throw new BackendApiError(
      response.status,
      await response.json().catch(() => undefined),
    );
  }
  return response.json();
}

export async function downloadPetAssetBackend(
  petId: string,
  assetId: string,
): Promise<Response> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.downloadPetAsset(petId, assetId);
  const response = await withAuthRawFetch((authHeaders) =>
    fetch(`${baseUrl}/api/v1/pet-life/pets/${petId}/assets/${assetId}`, {
      headers: authHeaders,
    }),
  );
  if (!response.ok) {
    throw new BackendApiError(response.status, undefined);
  }
  return response;
}

export async function deletePetAssetBackend(
  petId: string,
  assetId: string,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.deletePetAsset(petId, assetId);
  return withAuthVoid((headers) =>
    backendClient.DELETE("/api/v1/pet-life/pets/{pet_id}/assets/{asset_id}", {
      params: { path: { asset_id: assetId, pet_id: petId } },
      headers,
    }),
  );
}

export async function createBodyAssessmentBackend(
  petId: string,
  body: BodyAssessmentBody,
): Promise<BodyAssessmentMutationResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.createBodyAssessment(petId, body);
  return withAuth((headers) =>
    backendClient.POST("/api/v1/pet-life/pets/{pet_id}/body-assessments", {
      params: { path: { pet_id: petId } },
      body,
      headers,
    }),
  );
}

export async function listBodyAssessmentsBackend(
  petId: string,
): Promise<BodyAssessmentItem[]> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listBodyAssessments(petId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/pets/{pet_id}/body-assessments", {
      params: { path: { pet_id: petId } },
      headers,
    }),
  );
}

export async function listBreedsBackend(
  species?: "dog" | "cat",
): Promise<BreedListResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listBreeds(species);
  return unwrap(
    await backendClient.GET("/api/v1/knowledge/breeds", {
      params: { query: species ? { species } : {} },
    }),
  );
}

export async function searchBreedsBackend(
  query: string,
  species?: "dog" | "cat",
): Promise<BreedSearchResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.searchBreeds(query, species);
  return unwrap(
    await backendClient.GET("/api/v1/knowledge/search", {
      params: { query: { q: query, species } },
    }),
  );
}

export async function getBreedDetailBackend(
  breedId: string,
): Promise<BreedDetailResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getBreedDetail(breedId);
  return unwrap(
    await backendClient.GET("/api/v1/knowledge/breeds/{breed_id}", {
      params: { path: { breed_id: breedId } },
    }),
  );
}

export async function getPetKnowledgeBackend(
  petId: string,
): Promise<PetKnowledgeResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getPetKnowledge(petId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/knowledge/pets/{pet_id}", {
      params: { path: { pet_id: petId } },
      headers,
    }),
  );
}

export async function selectPetBreedBackend(
  petId: string,
  body: BreedSelectionBody,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.selectPetBreed(petId, body);
  await withAuth((headers) =>
    backendClient.PUT("/api/v1/pet-life/pets/{pet_id}/breed-selection", {
      params: { path: { pet_id: petId } },
      body,
      headers,
    }),
  );
}

export async function getPetCareGuidanceBackend(
  petId: string,
): Promise<CareGuidanceResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getPetCareGuidance(petId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/pets/{pet_id}/care-guidance", {
      params: { path: { pet_id: petId } },
      headers,
    }),
  );
}

export async function setGuidancePreferenceBackend(
  petId: string,
  guidanceId: string,
  body: GuidancePreferenceBody,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) {
    return developmentApi.setGuidancePreference(petId, guidanceId, body);
  }
  return withAuthVoid((headers) =>
    backendClient.PUT(
      "/api/v1/pet-life/pets/{pet_id}/care-guidance/{guidance_id}/preference",
      {
        params: { path: { guidance_id: guidanceId, pet_id: petId } },
        body,
        headers,
      },
    ),
  );
}

export async function getInventoryDetailBackend(
  unitId: string,
): Promise<InventoryDetailResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getInventoryDetail(unitId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/pet-life/inventory/{unit_id}", {
      params: { path: { unit_id: unitId } },
      headers,
    }),
  );
}

export async function openInventoryBackend(
  unitId: string,
  body: OpenInventoryBody,
) {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.openInventory(unitId, body);
  return withAuth((headers) =>
    backendClient.POST("/api/v1/pet-life/inventory/{unit_id}/open", {
      params: { path: { unit_id: unitId } },
      body,
      headers,
    }),
  );
}

export async function listOffersBackend(): Promise<OfferListItem[]> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listOffers();
  return unwrap(
    await backendClient.GET("/api/v1/catalog/offers", { cache: "no-store" }),
  );
}

export async function getOfferDetailBackend(
  offerId: string,
): Promise<OfferDetailResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getOfferDetail(offerId);
  return unwrap(
    await backendClient.GET("/api/v1/catalog/offers/{offer_id}", {
      params: { path: { offer_id: offerId } },
      cache: "no-store",
    }),
  );
}

export async function searchOffersBackend(
  q: string,
  limit: number,
  offset: number,
): Promise<OfferSearchPage> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.searchOffers(q, limit, offset);
  return unwrap(
    await backendClient.GET("/api/v1/catalog/offers/search", {
      params: { query: { q, limit, offset } },
      cache: "no-store",
    }),
  );
}

export async function listProductAlternativesBackend(
  productId: string,
): Promise<ProductAlternativeResponse[]> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listProductAlternatives(productId);
  return unwrap(
    await backendClient.GET(
      "/api/v1/catalog/products/{product_id}/alternatives",
      {
        params: { path: { product_id: productId } },
        cache: "no-store",
      },
    ),
  );
}

export async function createOrderBackend(
  body: CheckoutBody,
  idempotencyKey: string,
): Promise<OrderResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.createOrder(body, idempotencyKey);
  return withAuth((headers) =>
    backendClient.POST("/api/v1/checkout/orders", {
      body,
      headers,
      params: { header: { "Idempotency-Key": idempotencyKey } },
    }),
  );
}

export async function initiatePaymentBackend(
  orderId: string,
  body: PaymentRequestBody,
  idempotencyKey: string,
): Promise<PaymentRedirectResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) {
    return developmentApi.initiatePayment(orderId, body, idempotencyKey);
  }
  return withAuth((headers) =>
    backendClient.POST("/api/v1/orders/{order_id}/payments/zarinpal", {
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { order_id: orderId },
      },
      body,
      headers,
    }),
  );
}

export async function paymentCallbackBackend(
  authority: string,
  status: string | null,
): Promise<PaymentCallbackResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.paymentCallback(authority, status);
  return unwrap(
    await backendClient.GET("/api/v1/payments/zarinpal/callback", {
      params: { query: { Authority: authority, Status: status } },
      cache: "no-store",
    }),
  );
}

export async function listOrdersBackend(): Promise<OrderListPage> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.listOrders();
  return withAuth((headers) =>
    backendClient.GET("/api/v1/orders", { headers }),
  );
}

export async function acknowledgeOrderDelayBackend(
  orderId: string,
  idempotencyKey: string,
): Promise<DelayAcknowledgementResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) {
    return developmentApi.acknowledgeOrderDelay(orderId, idempotencyKey);
  }
  return withAuth((headers) =>
    backendClient.POST("/api/v1/orders/{order_id}/delay-acknowledgements", {
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { order_id: orderId },
      },
      headers,
    }),
  );
}

export async function getOrderDetailBackend(
  orderId: string,
): Promise<OrderDetailResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getOrderDetail(orderId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/orders/{order_id}", {
      params: { path: { order_id: orderId } },
      headers,
    }),
  );
}

export async function getOrderJourneyBackend(
  orderId: string,
): Promise<OrderJourneyResponse> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.getOrderJourney(orderId);
  return withAuth((headers) =>
    backendClient.GET("/api/v1/orders/{order_id}/journey", {
      params: { path: { order_id: orderId } },
      headers,
    }),
  );
}

export async function replaceOrderPetPlanBackend(
  orderId: string,
  body: OrderPetPlanBody,
): Promise<void> {
  const developmentApi = await loadDevelopmentApi();
  if (developmentApi) return developmentApi.replaceOrderPetPlan(orderId, body);
  return withAuthVoid((headers) =>
    backendClient.PUT("/api/v1/orders/{order_id}/pet-plan", {
      params: { path: { order_id: orderId } },
      body,
      headers,
    }),
  );
}
