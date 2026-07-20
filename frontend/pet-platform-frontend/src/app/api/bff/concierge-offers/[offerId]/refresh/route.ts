import { jsonError, jsonOk, requireCsrf } from "@/lib/api/bff-route";
import { refreshConciergeOfferBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ offerId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { offerId } = await context.params;
    return jsonOk(await refreshConciergeOfferBackend(offerId));
  } catch (error) {
    return jsonError(error);
  }
}
