import type { ConciergeOfferDeclineBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { declineConciergeOfferBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ offerId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { offerId } = await context.params;
    const body = await readJson<ConciergeOfferDeclineBody>(request);
    return jsonOk(await declineConciergeOfferBackend(offerId, body));
  } catch (error) {
    return jsonError(error);
  }
}
