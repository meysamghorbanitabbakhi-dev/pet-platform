import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getPoliciesBackend } from "@/lib/api/backend";

export async function GET() {
  try {
    return jsonOk(await getPoliciesBackend());
  } catch (error) {
    return jsonError(error);
  }
}
