import "server-only";

import createClient from "openapi-fetch";
import type { ApiPaths } from "@/lib/api-types";
import { offersFixture } from "@/lib/fixtures/gate-fixtures";
import { mapApiError } from "./errors";

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const fixtureMode = process.env.GATE_FIXTURE_MODE === "1";

const serverClient = createClient<ApiPaths>({
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

export async function listOffersServer() {
  if (fixtureMode) return offersFixture;
  return unwrap(
    await serverClient.GET("/api/v1/catalog/offers", { cache: "no-store" }),
  );
}
