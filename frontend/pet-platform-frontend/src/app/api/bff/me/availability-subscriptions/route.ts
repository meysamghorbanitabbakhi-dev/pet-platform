import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { listAvailabilitySubscriptionsBackend } from "@/lib/api/backend";

export async function GET() {
  try {
    return jsonOk(await listAvailabilitySubscriptionsBackend());
  } catch (error) {
    return jsonError(error);
  }
}
