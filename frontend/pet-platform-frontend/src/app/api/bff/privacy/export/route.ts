import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { exportMyDataBackend } from "@/lib/api/backend";

export async function GET() {
  try {
    return jsonOk(await exportMyDataBackend());
  } catch (error) {
    return jsonError(error);
  }
}
