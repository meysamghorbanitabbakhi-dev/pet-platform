import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getMeContextBackend } from "@/lib/api/backend";

export async function GET() {
  try {
    return jsonOk(await getMeContextBackend());
  } catch (error) {
    return jsonError(error);
  }
}
