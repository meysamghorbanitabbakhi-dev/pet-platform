import type { ReplenishmentReservationApproveBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { approveReplenishmentReservationBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ reservationId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { reservationId } = await context.params;
    const body = await readJson<ReplenishmentReservationApproveBody>(request);
    return jsonOk(
      await approveReplenishmentReservationBackend(reservationId, body),
    );
  } catch (error) {
    return jsonError(error);
  }
}
