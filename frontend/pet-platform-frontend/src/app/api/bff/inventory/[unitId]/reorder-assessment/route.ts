import { jsonError, jsonOk, requireCsrf } from "@/lib/api/bff-route";
import { assessReorderBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ unitId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { unitId } = await context.params;
    return jsonOk(await assessReorderBackend(unitId));
  } catch (error) {
    return jsonError(error);
  }
}
