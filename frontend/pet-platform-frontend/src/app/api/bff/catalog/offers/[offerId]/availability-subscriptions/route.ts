import { jsonError, jsonOk, requireCsrf } from "@/lib/api/bff-route";
import {
  cancelAvailabilitySubscriptionBackend,
  subscribeAvailabilityBackend,
} from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ offerId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { offerId } = await context.params;
    return jsonOk(await subscribeAvailabilityBackend(offerId));
  } catch (error) {
    return jsonError(error);
  }
}

export async function DELETE(
  request: Request,
  context: { params: Promise<{ offerId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { offerId } = await context.params;
    return jsonOk(await cancelAvailabilitySubscriptionBackend(offerId));
  } catch (error) {
    return jsonError(error);
  }
}
