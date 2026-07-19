import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getPrivacyRequestBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ requestId: string }> },
) {
  try {
    const { requestId } = await context.params;
    return jsonOk(await getPrivacyRequestBackend(requestId));
  } catch (error) {
    return jsonError(error);
  }
}
