import { jsonError, jsonNoContent, requireCsrf } from "@/lib/api/bff-route";
import { resumeJourneyBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ journeyId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { journeyId } = await context.params;
    await resumeJourneyBackend(journeyId);
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
