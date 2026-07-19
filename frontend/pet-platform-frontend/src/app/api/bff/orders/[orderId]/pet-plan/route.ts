import type { OrderPetPlanBody } from "@/lib/api-types";
import {
  jsonError,
  jsonNoContent,
  readJson,
  requireCsrf,
} from "@/lib/api/bff-route";
import { replaceOrderPetPlanBackend } from "@/lib/api/backend";

export async function PUT(
  request: Request,
  context: { params: Promise<{ orderId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { orderId } = await context.params;
    await replaceOrderPetPlanBackend(
      orderId,
      await readJson<OrderPetPlanBody>(request),
    );
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
