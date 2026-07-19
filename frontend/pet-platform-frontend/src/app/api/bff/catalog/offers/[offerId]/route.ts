import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getOfferDetailBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ offerId: string }> },
) {
  try {
    const { offerId } = await context.params;
    return jsonOk(await getOfferDetailBackend(offerId));
  } catch (error) {
    return jsonError(error);
  }
}
