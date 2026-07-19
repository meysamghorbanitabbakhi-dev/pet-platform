import { jsonError, jsonOk, requireCsrf } from "@/lib/api/bff-route";
import { acceptShelfLifeExceptionBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ orderId: string; exceptionId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { orderId, exceptionId } = await context.params;
    return jsonOk(await acceptShelfLifeExceptionBackend(orderId, exceptionId));
  } catch (error) {
    return jsonError(error);
  }
}
