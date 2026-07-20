import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getReplenishmentReservationBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ reservationId: string }> },
) {
  try {
    const { reservationId } = await context.params;
    return jsonOk(await getReplenishmentReservationBackend(reservationId));
  } catch (error) {
    return jsonError(error);
  }
}
