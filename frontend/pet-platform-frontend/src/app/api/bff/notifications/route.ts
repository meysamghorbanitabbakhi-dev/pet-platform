import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { listNotificationsBackend } from "@/lib/api/backend";

export async function GET() {
  try {
    return jsonOk(await listNotificationsBackend());
  } catch (error) {
    return jsonError(error);
  }
}
