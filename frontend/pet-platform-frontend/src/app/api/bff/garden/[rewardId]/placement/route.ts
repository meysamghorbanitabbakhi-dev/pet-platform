import type { GardenPlacementBody } from "@/lib/api-types";
import {
  jsonError,
  jsonNoContent,
  readJson,
  requireCsrf,
} from "@/lib/api/bff-route";
import {
  placeGardenObjectBackend,
  returnGardenObjectBackend,
} from "@/lib/api/backend";

export async function PUT(
  request: Request,
  context: { params: Promise<{ rewardId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { rewardId } = await context.params;
    await placeGardenObjectBackend(
      rewardId,
      await readJson<GardenPlacementBody>(request),
    );
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}

export async function DELETE(
  request: Request,
  context: { params: Promise<{ rewardId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { rewardId } = await context.params;
    await returnGardenObjectBackend(rewardId);
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
