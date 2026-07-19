import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { listProductAlternativesBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ productId: string }> },
) {
  try {
    const { productId } = await context.params;
    return jsonOk(await listProductAlternativesBackend(productId));
  } catch (error) {
    return jsonError(error);
  }
}
