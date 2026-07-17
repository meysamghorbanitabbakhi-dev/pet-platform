"use client";

import createClient from "openapi-fetch";
import type {
  AddressBody,
  ApiPaths,
  HouseholdBody,
  OpenInventoryBody,
  OtpRequestBody,
  OtpVerifyBody,
  PetBody,
} from "@/lib/api-types";
import {
  ids,
  incomingTodayFixture,
  journeyOffersFixture,
  meContextFixture,
  openedEstimateFixture,
  policyFixture,
  rexTodayFixture,
  returningTodayFixture,
} from "@/lib/fixtures/gate-fixtures";
import { authHeaders, setAccessToken } from "@/lib/session";
import { mapApiError } from "./errors";

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const fixtureMode = process.env.NEXT_PUBLIC_GATE_FIXTURE_MODE === "1";

export const apiClient = createClient<ApiPaths>({
  baseUrl,
  credentials: "include",
});

async function unwrap<T>(result: {
  data?: T;
  error?: unknown;
  response: Response;
}): Promise<T> {
  if (result.error || !result.data) {
    throw mapApiError(result.response.status, result.error);
  }
  return result.data;
}

export async function requestOtp(body: OtpRequestBody) {
  if (fixtureMode) {
    return { challenge_id: ids.journey, expires_in_seconds: 90 };
  }
  return unwrap(await apiClient.POST("/api/v1/auth/otp/request", { body }));
}

export async function verifyOtp(body: OtpVerifyBody) {
  if (fixtureMode) {
    if (body.code === "000000")
      return {
        state: "invalid" as const,
        attempts_remaining: 2,
        expires_in_seconds: 60,
      };
    if (body.code === "999999")
      return {
        state: "locked" as const,
        attempts_remaining: 0,
        expires_in_seconds: 900,
      };
    const response = {
      access_token: "fixture-access-token",
      identity_id: "99999999-9999-4999-8999-999999999999",
      refresh_token: "fixture-refresh-token",
      state: "verified" as const,
      token_type: "bearer" as const,
    };
    setAccessToken(response.access_token);
    return response;
  }
  const response = await unwrap(
    await apiClient.POST("/api/v1/auth/otp/verify", { body }),
  );
  setAccessToken(response.access_token);
  return response;
}

export async function getPolicies() {
  if (fixtureMode) return policyFixture;
  return unwrap(
    await apiClient.GET("/api/v1/system/policies", { headers: authHeaders() }),
  );
}

export async function getMeContext() {
  if (fixtureMode) return meContextFixture;
  return unwrap(
    await apiClient.GET("/api/v1/me/context", { headers: authHeaders() }),
  );
}

export async function createHousehold(body: HouseholdBody) {
  if (fixtureMode) return { id: ids.household };
  return unwrap(
    await apiClient.POST("/api/v1/pet-life/households", {
      body,
      headers: authHeaders(),
    }),
  );
}

export async function createPet(householdId: string, body: PetBody) {
  if (fixtureMode) return { id: ids.petBishi };
  return unwrap(
    await apiClient.POST("/api/v1/pet-life/households/{household_id}/pets", {
      params: { path: { household_id: householdId } },
      body,
      headers: authHeaders(),
    }),
  );
}

export async function createAddress(householdId: string, body: AddressBody) {
  if (fixtureMode) return { id: "abababab-abab-4aba-8aba-abababababab" };
  return unwrap(
    await apiClient.POST(
      "/api/v1/pet-life/households/{household_id}/addresses",
      {
        params: { path: { household_id: householdId } },
        body,
        headers: authHeaders(),
      },
    ),
  );
}

export async function getToday(petId: string) {
  if (fixtureMode)
    return petId === ids.petRex ? rexTodayFixture : returningTodayFixture;
  return unwrap(
    await apiClient.GET("/api/v1/pet-life/pets/{pet_id}/today", {
      params: { path: { pet_id: petId } },
      headers: authHeaders(),
    }),
  );
}

export async function getIncomingToday() {
  if (fixtureMode) return incomingTodayFixture;
  return getToday(ids.petBishi);
}

export async function getJourneyOffers(petId: string) {
  if (fixtureMode) return journeyOffersFixture;
  return unwrap(
    await apiClient.GET("/api/v1/pet-life/pets/{pet_id}/journey-offers", {
      params: { path: { pet_id: petId } },
      headers: authHeaders(),
    }),
  );
}

export async function openInventory(unitId: string, body: OpenInventoryBody) {
  if (fixtureMode) return openedEstimateFixture;
  return unwrap(
    await apiClient.POST("/api/v1/pet-life/inventory/{unit_id}/open", {
      params: { path: { unit_id: unitId } },
      body,
      headers: authHeaders(),
    }),
  );
}
