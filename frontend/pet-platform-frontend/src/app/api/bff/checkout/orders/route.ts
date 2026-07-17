import type { CheckoutBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { createOrderBackend } from "@/lib/api/backend";

type CreateOrderRequest = {
  body: CheckoutBody;
  idempotencyKey: string;
};

export async function POST(request: Request) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const payload = await readJson<CreateOrderRequest>(request);
    return jsonOk(
      await createOrderBackend(payload.body, payload.idempotencyKey),
    );
  } catch (error) {
    return jsonError(error);
  }
}
