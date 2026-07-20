import type { ReplenishmentReservationDeclineBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { declineReplenishmentReservationBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ reservationId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { reservationId } = await context.params;
    const body = await readJson<ReplenishmentReservationDeclineBody>(request);
    return jsonOk(
      await declineReplenishmentReservationBackend(reservationId, body),
    );
  } catch (error) {
    return jsonError(error);
  }
}
