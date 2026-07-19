import type { PetBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { createPetBackend, listHouseholdPetsBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ householdId: string }> },
) {
  try {
    const { householdId } = await context.params;
    return jsonOk(await listHouseholdPetsBackend(householdId));
  } catch (error) {
    return jsonError(error);
  }
}

export async function POST(
  request: Request,
  context: { params: Promise<{ householdId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { householdId } = await context.params;
    return jsonOk(
      await createPetBackend(householdId, await readJson<PetBody>(request)),
    );
  } catch (error) {
    return jsonError(error);
  }
}
