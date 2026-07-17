import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { listHouseholdInventoryBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ householdId: string }> },
) {
  try {
    const { householdId } = await context.params;
    return jsonOk(await listHouseholdInventoryBackend(householdId));
  } catch (error) {
    return jsonError(error);
  }
}
