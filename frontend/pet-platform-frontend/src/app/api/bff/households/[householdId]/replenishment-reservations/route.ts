import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { listReplenishmentReservationsBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ householdId: string }> },
) {
  try {
    const { householdId } = await context.params;
    return jsonOk(await listReplenishmentReservationsBackend(householdId));
  } catch (error) {
    return jsonError(error);
  }
}
