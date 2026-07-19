import type { PaymentRequestBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { initiatePaymentBackend } from "@/lib/api/backend";

type InitiatePaymentRequest = {
  body: PaymentRequestBody;
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
    const payload = await readJson<InitiatePaymentRequest>(request);
    return jsonOk(
      await initiatePaymentBackend(
        orderId,
        payload.body,
        payload.idempotencyKey,
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
