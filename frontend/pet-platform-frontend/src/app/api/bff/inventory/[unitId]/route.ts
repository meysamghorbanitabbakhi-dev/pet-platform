import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getInventoryDetailBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ unitId: string }> },
) {
  try {
    const { unitId } = await context.params;
    return jsonOk(await getInventoryDetailBackend(unitId));
  } catch (error) {
    return jsonError(error);
  }
}
