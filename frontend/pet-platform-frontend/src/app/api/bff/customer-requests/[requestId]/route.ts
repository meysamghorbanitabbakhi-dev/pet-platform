import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getCustomerRequestBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ requestId: string }> },
) {
  try {
    const { requestId } = await context.params;
    return jsonOk(await getCustomerRequestBackend(requestId));
  } catch (error) {
    return jsonError(error);
  }
}
