import type { PetProfilePatch } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { updatePetProfileBackend } from "@/lib/api/backend";

export async function PATCH(
  request: Request,
  context: { params: Promise<{ petId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { petId } = await context.params;
    return jsonOk(
      await updatePetProfileBackend(
        petId,
        await readJson<PetProfilePatch>(request),
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
