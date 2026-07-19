import { jsonError, jsonOk, requireCsrf } from "@/lib/api/bff-route";
import { acknowledgeOrderDelayBackend } from "@/lib/api/backend";

type AcknowledgeDelayPayload = {
  idempotencyKey: string;
};

export async function POST(
  request: Request,
  context: { params: Promise<{ orderId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { orderId } = await context.params;
    const payload = (await request.json()) as AcknowledgeDelayPayload;
    return jsonOk(
      await acknowledgeOrderDelayBackend(orderId, payload.idempotencyKey),
    );
  } catch (error) {
    return jsonError(error);
  }
}
