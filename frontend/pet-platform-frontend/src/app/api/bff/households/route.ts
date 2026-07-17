import type { HouseholdBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { createHouseholdBackend } from "@/lib/api/backend";

export async function POST(request: Request) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    return jsonOk(
      await createHouseholdBackend(await readJson<HouseholdBody>(request)),
    );
  } catch (error) {
    return jsonError(error);
  }
}
