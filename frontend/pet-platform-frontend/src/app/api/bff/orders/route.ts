import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { listOrdersBackend } from "@/lib/api/backend";

export async function GET() {
  try {
    return jsonOk(await listOrdersBackend());
  } catch (error) {
    return jsonError(error);
  }
}
