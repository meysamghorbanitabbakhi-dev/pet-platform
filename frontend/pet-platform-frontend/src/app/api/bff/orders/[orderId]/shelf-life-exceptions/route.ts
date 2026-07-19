import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { listShelfLifeExceptionsBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ orderId: string }> },
) {
  try {
    const { orderId } = await context.params;
    return jsonOk(await listShelfLifeExceptionsBackend(orderId));
  } catch (error) {
    return jsonError(error);
  }
}
