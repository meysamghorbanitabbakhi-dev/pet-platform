import type { JourneyStopBody } from "@/lib/api-types";
import { jsonError, jsonNoContent, readJson, requireCsrf } from "@/lib/api/bff-route";
import { stopJourneyBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ journeyId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { journeyId } = await context.params;
    await stopJourneyBackend(journeyId, await readJson<JourneyStopBody>(request));
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
