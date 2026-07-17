import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getOrderJourneyBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ orderId: string }> },
) {
  try {
    const { orderId } = await context.params;
    return jsonOk(await getOrderJourneyBackend(orderId));
  } catch (error) {
    return jsonError(error);
  }
}
