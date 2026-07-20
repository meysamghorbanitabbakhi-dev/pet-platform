import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { listConciergeOffersBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ requestId: string }> },
) {
  try {
    const { requestId } = await context.params;
    return jsonOk(await listConciergeOffersBackend(requestId));
  } catch (error) {
    return jsonError(error);
  }
}
