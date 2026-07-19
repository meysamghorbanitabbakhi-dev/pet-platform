import type { JourneyCompleteBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { completeJourneyBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ journeyId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { journeyId } = await context.params;
    return jsonOk(
      await completeJourneyBackend(
        journeyId,
        await readJson<JourneyCompleteBody>(request),
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
