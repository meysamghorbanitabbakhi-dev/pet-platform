import type { OrderCancellationBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { cancelOrderBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ orderId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { orderId } = await context.params;
    const body = await readJson<OrderCancellationBody>(request);
    return jsonOk(await cancelOrderBackend(orderId, body));
  } catch (error) {
    return jsonError(error);
  }
}
