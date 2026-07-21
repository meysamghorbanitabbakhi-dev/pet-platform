import type { BreedSelectionBody } from "@/lib/api-types";
import {
  jsonError,
  jsonNoContent,
  readJson,
  requireCsrf,
} from "@/lib/api/bff-route";
import { selectPetBreedBackend } from "@/lib/api/backend";

export async function PUT(
  request: Request,
  context: { params: Promise<{ petId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { petId } = await context.params;
    await selectPetBreedBackend(
      petId,
      await readJson<BreedSelectionBody>(request),
    );
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
