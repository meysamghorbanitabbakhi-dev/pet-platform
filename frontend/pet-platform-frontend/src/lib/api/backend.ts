import "server-only";

import createClient from "openapi-fetch";
import type {
  AddressBody,
  ApiPaths,
  HouseholdBody,
  InventoryDetailResponse,
  JourneyOfferResponse,
  MeContextResponse,
  OfferListItem,
  OpenInventoryBody,
  OtpRequestBody,
  OtpRequestResponse,
  OtpVerifyBody,
  OtpVerifyResponse,
  PetBody,
  PetProfilePatch,
  PolicyResponse,
  TodayResponse,
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
