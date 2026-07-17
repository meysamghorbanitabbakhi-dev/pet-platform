import { jsonError, jsonNoContent, requireCsrf } from "@/lib/api/bff-route";
import { exhaustInventoryBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ unitId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { unitId } = await context.params;
    await exhaustInventoryBackend(unitId);
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
