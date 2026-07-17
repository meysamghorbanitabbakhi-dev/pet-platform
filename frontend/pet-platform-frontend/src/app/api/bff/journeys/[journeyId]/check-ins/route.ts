import type { JourneyCheckInBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { submitCheckInBackend } from "@/lib/api/backend";

type CheckInRequest = {
  body: JourneyCheckInBody;
  idempotencyKey: string;
};

export async function POST(
  request: Request,
  context: { params: Promise<{ journeyId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { journeyId } = await context.params;
    const payload = await readJson<CheckInRequest>(request);
    return jsonOk(
      await submitCheckInBackend(
        journeyId,
        payload.body,
        payload.idempotencyKey,
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
