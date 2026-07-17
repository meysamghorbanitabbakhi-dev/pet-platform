import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getOrderDetailBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ orderId: string }> },
) {
  try {
    const { orderId } = await context.params;
    return jsonOk(await getOrderDetailBackend(orderId));
  } catch (error) {
    return jsonError(error);
  }
}
