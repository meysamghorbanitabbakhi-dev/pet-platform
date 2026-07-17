"use client";

import type {
  AddressBody,
  FoodEstimateResponse,
  HouseholdBody,
  IdResponse,
  InventoryDetailResponse,
  JourneyOfferResponse,
  MeContextResponse,
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
